
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.repositories.job_repository import ProcessingJobRepository
from app.db.session import SessionLocal
from app.domain.extraction.csv_extractor import extract_text_from_csv
from app.domain.extraction.docx_extractor import extract_text_from_docx
from app.domain.extraction.file_discovery import discover_supported_files
from app.domain.extraction.pdf_extractor import extract_text_from_pdf
from app.domain.extraction.txt_extractor import extract_text_from_txt
from app.domain.pii.detectors import find_sensitive_matches
from app.domain.pii.scrubber import scrub_document_text


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}


@dataclass(frozen=True)
class ProcessedFile:
    file_name: str
    status: str
    safe_to_send: bool
    redacted_count: int = 0
    warnings: list[str] = field(default_factory=list)
    scrubbed_output: str | None = None


@dataclass(frozen=True)
class TrustedBatchResult:
    job_type: str
    safe_to_send: bool
    status: str
    success_count: int
    failed_count: int
    combined_output: str
    processed_files: list[ProcessedFile]
    failed_files: list[dict[str, str]]

    def to_repository_dict(self) -> dict[str, object]:
        return {
            "job_type": self.job_type,
            "safe_to_send": self.safe_to_send,
            "status": self.status,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "combined_output": self.combined_output,
            "processed_files": [
                {
                    "file_name": item.file_name,
                    "status": item.status,
                    "safe_to_send": item.safe_to_send,
                    "redacted_count": item.redacted_count,
                    "warnings": item.warnings,
                    "scrubbed_output": item.scrubbed_output,
                }
                for item in self.processed_files
            ],
            "failed_files": list(self.failed_files),
        }


class DocumentProcessingService:
    """Process supported files locally and return scrubbed output."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser().resolve()

    def discover_files(self) -> list[Path]:
        return discover_supported_files(self.data_dir)

    def extract_text(self, file_path: str | Path) -> str:
        path = Path(file_path).resolve()
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return extract_text_from_pdf(path)
        if suffix == ".docx":
            return extract_text_from_docx(path)
        if suffix == ".csv":
            return extract_text_from_csv(path)
        if suffix == ".txt":
            return extract_text_from_txt(path)

        raise ValueError("Unsupported file type.")

    def _validate_files(
        self,
        file_paths: list[str | Path],
        max_file_size_bytes: int | None = None,
    ) -> tuple[list[Path], list[dict[str, str]]]:
        validated: list[Path] = []
        failed: list[dict[str, str]] = []
        seen: set[Path] = set()

        for supplied_path in file_paths:
            try:
                path = Path(supplied_path).expanduser().resolve(strict=True)
                path.relative_to(self.data_dir)

                if path in seen:
                    failed.append({
                        "file": path.name,
                        "reason": "Duplicate file rejected.",
                    })
                    continue

                seen.add(path)

                if not path.is_file():
                    raise ValueError("Not a regular file.")

                if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    failed.append({
                        "file": path.name,
                        "reason": "Unsupported file extension.",
                    })
                    continue

                if (
                    max_file_size_bytes is not None
                    and path.stat().st_size > max_file_size_bytes
                ):
                    failed.append({
                        "file": path.name,
                        "reason": "File exceeds configured size limit.",
                    })
                    continue

                validated.append(path)

            except (OSError, ValueError, TypeError):
                failed.append({
                    "file": "unavailable",
                    "reason": "File failed path or accessibility validation.",
                })

        return validated, failed

    def process_directory(
        self,
        file_paths: list[str | Path] | None = None,
        max_file_size_bytes: int | None = None,
    ) -> dict[str, object]:
        # Use the exact paths supplied by the API.
        # Discovery is retained for isolated service tests and local use.
        supplied_files = (
            file_paths if file_paths is not None else self.discover_files()
        )

        if not isinstance(supplied_files, list):
            return {
                "success_count": 0,
                "failed_count": 1,
                "combined_output": "",
                "processed_files": [],
                "failed_files": [{
                    "file": "unavailable",
                    "reason": "Invalid file list.",
                }],
                "safe_to_send": False,
                "status": "unsafe_batch",
            }

        validated_files, validation_failures = self._validate_files(
            supplied_files,
            max_file_size_bytes=max_file_size_bytes,
        )

        if validation_failures:
            return {
                "success_count": 0,
                "failed_count": len(validation_failures),
                "combined_output": "",
                "processed_files": [],
                "failed_files": validation_failures,
                "safe_to_send": False,
                "status": "unsafe_batch",
            }

        if not validated_files:
            return {
                "success_count": 0,
                "failed_count": 0,
                "combined_output": "",
                "processed_files": [],
                "failed_files": [],
                "safe_to_send": False,
                "status": "empty_batch",
            }

        successful: list[ProcessedFile] = []
        failed: list[dict[str, str]] = []
        combined_sections: list[str] = []

        for file_path in validated_files:
            file_name = file_path.name

            try:
                # Recheck the path immediately before extraction.
                current_path = file_path.resolve(strict=True)
                current_path.relative_to(self.data_dir)

                if not current_path.is_file():
                    raise ValueError("File is no longer accessible.")

                suffix = current_path.suffix.lower()

                if suffix not in ALLOWED_EXTENSIONS:
                    raise ValueError("File extension changed.")

                if (
                    max_file_size_bytes is not None
                    and current_path.stat().st_size > max_file_size_bytes
                ):
                    raise ValueError("File exceeds configured size limit.")

                is_csv = suffix == ".csv"

                extracted_text = self.extract_text(current_path)

                scrubbed = scrub_document_text(
                    extracted_text,
                    is_csv=is_csv,
                )

                if not scrubbed.safe_to_send:
                    failed.append({
                        "file": file_name,
                        "reason": "Document did not pass scrubbing validation.",
                    })
                    continue

                if (
                    not isinstance(scrubbed.text, str)
                    or not scrubbed.text.strip()
                ):
                    failed.append({
                        "file": file_name,
                        "reason": "Scrubbing returned empty output.",
                    })
                    continue

                residual_matches = find_sensitive_matches(
                    scrubbed.text,
                    is_csv=is_csv,
                )

                if residual_matches:
                    failed.append({
                        "file": file_name,
                        "reason": "Independent safety validation failed.",
                    })
                    continue

                safe_output = scrubbed.text.strip()

                combined_sections.append(
                    f"=== {file_name} ===\n{safe_output}"
                )

                successful.append(
                    ProcessedFile(
                        file_name=file_name,
                        status="success",
                        safe_to_send=True,
                        redacted_count=scrubbed.redacted_count,
                        warnings=[],
                        scrubbed_output=safe_output,
                    )
                )

            except Exception:
                failed.append({
                    "file": file_name,
                    "reason": (
                        "Extraction or validation failed. "
                        "Raw content was not returned."
                    ),
                })

        batch_safe_to_send = bool(successful) and not failed

        return {
            "success_count": len(successful),
            "failed_count": len(failed),
            "combined_output": "\n\n".join(combined_sections),
            "processed_files": [
                item.__dict__ for item in successful
            ],
            "failed_files": failed,
            "safe_to_send": batch_safe_to_send,
            "status": (
                "success" if batch_safe_to_send else "unsafe_batch"
            ),
        }

    def _create_trusted_batch_result(
        self,
        batch_result: dict[str, object],
    ) -> TrustedBatchResult:
        if not isinstance(batch_result, dict):
            raise ValueError("Invalid batch result.")

        if batch_result.get("safe_to_send") is not True:
            raise ValueError("Batch is not safe to persist.")

        if batch_result.get("status") != "success":
            raise ValueError("Batch was not successful.")

        failed_count = batch_result.get("failed_count")
        success_count = batch_result.get("success_count")
        failed_files = batch_result.get("failed_files")
        processed_files = batch_result.get("processed_files")
        combined_output = batch_result.get("combined_output")

        if type(failed_count) is not int or failed_count != 0:
            raise ValueError("Batch contains failed files.")

        if not isinstance(failed_files, list) or failed_files:
            raise ValueError("Failed file list must be empty.")

        if type(success_count) is not int or success_count <= 0:
            raise ValueError("Invalid successful-file count.")

        if not isinstance(processed_files, list) or not processed_files:
            raise ValueError("No processed files were supplied.")

        if success_count != len(processed_files):
            raise ValueError("Successful-file count mismatch.")

        if not isinstance(combined_output, str) or not combined_output.strip():
            raise ValueError("Combined output is empty.")

        trusted_files: list[ProcessedFile] = []
        expected_sections: list[str] = []
        seen_names: set[str] = set()

        for item in processed_files:
            if not isinstance(item, dict):
                raise ValueError("Malformed processed-file entry.")

            file_name = item.get("file_name")
            output = item.get("scrubbed_output")
            redacted_count = item.get("redacted_count")
            warnings = item.get("warnings")

            if item.get("status") != "success":
                raise ValueError("A processed file was not successful.")

            if item.get("safe_to_send") is not True:
                raise ValueError("A processed file was not marked safe.")

            if not isinstance(file_name, str) or not file_name.strip():
                raise ValueError("Invalid filename.")

            if Path(file_name).name != file_name or file_name in {".", ".."}:
                raise ValueError("Invalid filename.")

            if file_name in seen_names:
                raise ValueError("Duplicate filenames are not allowed.")

            seen_names.add(file_name)

            if not isinstance(output, str) or not output.strip():
                raise ValueError("Scrubbed output is empty.")

            if type(redacted_count) is not int or redacted_count < 0:
                raise ValueError("Invalid redaction count.")

            if not isinstance(warnings, list) or warnings:
                raise ValueError("Warnings must be an empty list.")

            is_csv = Path(file_name).suffix.lower() == ".csv"

            if find_sensitive_matches(output, is_csv=is_csv):
                raise ValueError(
                    "Document failed independent safety validation."
                )

            safe_output = output.strip()

            expected_sections.append(
                f"=== {file_name} ===\n{safe_output}"
            )

            trusted_files.append(
                ProcessedFile(
                    file_name=file_name,
                    status="success",
                    safe_to_send=True,
                    redacted_count=redacted_count,
                    warnings=[],
                    scrubbed_output=safe_output,
                )
            )

        expected_combined = "\n\n".join(expected_sections)

        if combined_output != expected_combined:
            raise ValueError(
                "Combined output does not match individual files."
            )

        # Combined output contains multiple formats and section headings.
        # Validate it as ordinary text, not as a single CSV document.
        if find_sensitive_matches(combined_output, is_csv=False):
            raise ValueError(
                "Combined output failed independent safety validation."
            )

        return TrustedBatchResult(
            job_type="document_scan",
            safe_to_send=True,
            status="success",
            success_count=success_count,
            failed_count=0,
            combined_output=expected_combined,
            processed_files=trusted_files,
            failed_files=[],
        )

    def persist_batch_result(
        self,
        batch_result: TrustedBatchResult,
        db_session: Session | None = None,
    ) -> object:
        """Persist a structurally validated batch through repository safeguards."""

        if not isinstance(batch_result, TrustedBatchResult):
            raise TypeError("A TrustedBatchResult is required.")

        session = db_session or SessionLocal()
        repository = ProcessingJobRepository(session)

        try:
            job = repository.persist_successful_batch(
                batch_result.job_type,
                batch_result.to_repository_dict(),
            )
            session.commit()
            return job
        except Exception:
            session.rollback()
            raise
        finally:
            if db_session is None:
                session.close()
