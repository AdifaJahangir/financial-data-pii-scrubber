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
from app.domain.pii.scrubber import scrub_document_text


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
    """Process supported files locally and return a combined scrubbed output."""

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
        raise ValueError(f"Unsupported file type: {suffix}")

    def process_directory(self) -> dict[str, object]:
        discovered_files = self.discover_files()
        successful: list[ProcessedFile] = []
        failed: list[dict[str, str]] = []
        combined_sections: list[str] = []

        if not discovered_files:
            return {
                "success_count": 0,
                "failed_count": 0,
                "combined_output": "",
                "processed_files": [],
                "failed_files": [],
                "safe_to_send": False,
                "status": "empty_batch",
            }

        for file_path in discovered_files:
            file_name = file_path.name
            try:
                extracted_text = self.extract_text(file_path)
                scrubbed = scrub_document_text(extracted_text)
                if not scrubbed.safe_to_send:
                    failed.append({"file": file_name, "reason": scrubbed.warnings[0] if scrubbed.warnings else "Scrubbing failed."})
                    continue

                combined_sections.append(f"=== {file_name} ===\n{scrubbed.text.strip()}")
                successful.append(
                    ProcessedFile(
                        file_name=file_name,
                        status="success",
                        safe_to_send=True,
                        redacted_count=scrubbed.redacted_count,
                        warnings=[],
                        scrubbed_output=scrubbed.text.strip(),
                    )
                )
            except Exception:  # pragma: no cover - defensive path
                failed.append({"file": file_name, "reason": "Extraction or validation failed. Raw content was not returned."})

        batch_safe_to_send = len(successful) > 0 and len(failed) == 0
        result = {
            "success_count": len(successful),
            "failed_count": len(failed),
            "combined_output": "\n\n".join(combined_sections),
            "processed_files": [item.__dict__ for item in successful],
            "failed_files": failed,
            "safe_to_send": batch_safe_to_send,
            "status": "success" if batch_safe_to_send else "unsafe_batch",
        }
        return result

    def _create_trusted_batch_result(self, batch_result: dict[str, object]) -> TrustedBatchResult:
        if not isinstance(batch_result, dict):
            raise ValueError("Batch result must be a dictionary created by the local processing pipeline.")

        safe_to_send = batch_result.get("safe_to_send")
        status = batch_result.get("status")
        failed_count = batch_result.get("failed_count")
        success_count = batch_result.get("success_count")
        failed_files = batch_result.get("failed_files")
        processed_files = batch_result.get("processed_files")
        combined_output = batch_result.get("combined_output")

        if safe_to_send is not True:
            raise ValueError("Batch result is not marked safe to send.")
        if status != "success":
            raise ValueError("Batch result is not a successful pipeline result.")
        if not isinstance(failed_count, int) or failed_count != 0:
            raise ValueError("Batch result contains failed files and cannot be persisted.")
        if not isinstance(failed_files, list) or failed_files != []:
            raise ValueError("Failed file list must be empty for a successful batch.")
        if not isinstance(success_count, int) or success_count <= 0:
            raise ValueError("Batch does not contain a valid successful-file count.")
        if not isinstance(processed_files, list) or not processed_files:
            raise ValueError("Batch does not contain processed files.")
        if success_count != len(processed_files):
            raise ValueError("Success count does not match processed file entries.")
        if not isinstance(combined_output, str) or not combined_output.strip():
            raise ValueError("Combined output cannot be empty for a successful batch.")

        trusted_files: list[ProcessedFile] = []
        for item in processed_files:
            if not isinstance(item, dict):
                raise ValueError("A processed file entry is malformed.")
            if item.get("status") != "success":
                raise ValueError("Processed file was not marked successful.")
            if item.get("safe_to_send") is not True:
                raise ValueError("Processed file was not marked safe to send.")
            if not isinstance(item.get("file_name"), str) or not item["file_name"].strip():
                raise ValueError("Processed file is missing a valid file name.")
            if not isinstance(item.get("scrubbed_output"), str) or not item["scrubbed_output"].strip():
                raise ValueError("Processed file has empty scrubbed output.")
            if not isinstance(item.get("redacted_count"), int) or item["redacted_count"] < 0:
                raise ValueError("Processed file has invalid redacted_count.")
            trusted_files.append(
                ProcessedFile(
                    file_name=item["file_name"],
                    status=item["status"],
                    safe_to_send=item["safe_to_send"],
                    redacted_count=item["redacted_count"],
                    warnings=item.get("warnings") if isinstance(item.get("warnings"), list) else [],
                    scrubbed_output=item["scrubbed_output"],
                )
            )

        return TrustedBatchResult(
            job_type="document_scan",
            safe_to_send=True,
            status="success",
            success_count=success_count,
            failed_count=0,
            combined_output=combined_output,
            processed_files=trusted_files,
            failed_files=[],
        )

    def persist_batch_result(self, batch_result: TrustedBatchResult, db_session: Session | None = None) -> object:
        """Persist results only from the existing local processing pipeline.

        Arbitrary dictionaries are rejected at this boundary. A result must be created by
        _create_trusted_batch_result() only after the local extraction + scrubbing + fail-closed
        checks have already succeeded.
        """
        if not isinstance(batch_result, TrustedBatchResult):
            raise TypeError("persist_batch_result() requires a TrustedBatchResult produced by the local pipeline.")

        session = db_session or SessionLocal()
        repository = ProcessingJobRepository(session)
        try:
            job = repository.persist_successful_batch(batch_result.job_type, batch_result.to_repository_dict())
            session.commit()
            return job
        except Exception:
            session.rollback()
            raise
        finally:
            if db_session is None:
                session.close()
