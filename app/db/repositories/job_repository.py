
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import ProcessingJob, ScrubbedDocument
from app.domain.pii.detectors import find_sensitive_matches


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def _validate_success_batch(self, batch_result: dict[str, object]) -> None:
        if not isinstance(batch_result, dict):
            raise ValueError("Batch result must be a dictionary.")

        job_type = batch_result.get("job_type")
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("Batch job type is required.")

        if batch_result.get("safe_to_send") is not True:
            raise ValueError("Batch is not safe to persist.")

        if batch_result.get("status") != "success":
            raise ValueError("Successful batch status mismatch.")

        failed_count = batch_result.get("failed_count")
        success_count = batch_result.get("success_count")
        failed_files = batch_result.get("failed_files")
        processed_files = batch_result.get("processed_files")
        combined_output = batch_result.get("combined_output")

        if type(failed_count) is not int or failed_count != 0:
            raise ValueError("Failed files are present.")

        if not isinstance(failed_files, list) or failed_files:
            raise ValueError("Failed file list must be empty.")

        if type(success_count) is not int or success_count <= 0:
            raise ValueError("At least one successful file is required.")

        if not isinstance(processed_files, list) or not processed_files:
            raise ValueError("No processed files were available.")

        if success_count != len(processed_files):
            raise ValueError("Success count does not match processed files.")

        if not isinstance(combined_output, str) or not combined_output.strip():
            raise ValueError("Combined output is empty.")

        expected_sections: list[str] = []
        seen_file_names: set[str] = set()

        for item in processed_files:
            if not isinstance(item, dict):
                raise ValueError("Processed file metadata is invalid.")

            if item.get("status") != "success":
                raise ValueError("A processed file was not successful.")

            if item.get("safe_to_send") is not True:
                raise ValueError("A processed file was not marked safe.")

            file_name = item.get("file_name")

            if not isinstance(file_name, str) or not file_name.strip():
                raise ValueError("A processed file has an invalid filename.")

            if (
                Path(file_name).name != file_name
                or file_name in {".", ".."}
                or "/" in file_name
                or "\\" in file_name
            ):
                raise ValueError("Invalid processed filename.")

            if file_name in seen_file_names:
                raise ValueError(
                    "Duplicate processed filenames are not allowed."
                )

            seen_file_names.add(file_name)

            redacted_count = item.get("redacted_count")
            if type(redacted_count) is not int or redacted_count < 0:
                raise ValueError("Invalid redaction count.")

            warnings = item.get("warnings")

            if warnings is not None and (
                not isinstance(warnings, list)
                or any(not isinstance(warning, str) for warning in warnings)
            ):
                raise ValueError("Malformed warning metadata.")

            if warnings:
                raise ValueError("Files with warnings cannot be persisted.")

            scrubbed_output = item.get("scrubbed_output")

            if (
                not isinstance(scrubbed_output, str)
                or not scrubbed_output.strip()
            ):
                raise ValueError("Scrubbed output is empty.")

            # Apply strict CSV validation to CSV files.
            is_csv = Path(file_name).suffix.lower() == ".csv"

            if find_sensitive_matches(
                scrubbed_output,
                is_csv=is_csv,
            ):
                raise ValueError(
                    "Independent safety validation rejected a document."
                )

            expected_sections.append(
                f"=== {file_name} ===\n{scrubbed_output}"
            )

        # Confirm that combined output exactly matches individual outputs.
        expected_combined_output = "\n\n".join(expected_sections)

        if combined_output != expected_combined_output:
            raise ValueError(
                "Combined output does not match individual document outputs."
            )

        # Combined output contains multiple formats and section headings.
        # Validate it as ordinary text, not as one CSV document.
        if find_sensitive_matches(
            combined_output,
            is_csv=False,
        ):
            raise ValueError(
                "Independent safety validation rejected combined output."
            )

    def persist_successful_batch(
        self,
        job_type: str,
        batch_result: dict[str, object],
    ) -> ProcessingJob:
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("Job type must be a non-empty string.")

        if not isinstance(batch_result, dict):
            raise ValueError("Batch result must be a dictionary.")

        validated_batch = {
            **batch_result,
            "job_type": job_type,
        }

        self._validate_success_batch(validated_batch)

        job = ProcessingJob(
            job_type=job_type,
            status="success",
            safe_to_send=True,
            success_count=batch_result["success_count"],
            failed_count=0,
            combined_output=batch_result["combined_output"],
            details="Successful batch persistence only.",
        )

        self.session.add(job)
        self.session.flush()

        for item in batch_result["processed_files"]:
            document = ScrubbedDocument(
                processing_job_id=job.id,
                file_name=item["file_name"],
                status="success",
                safe_to_send=True,
                redacted_count=item["redacted_count"],
                warnings=None,
                scrubbed_output=item["scrubbed_output"],
            )
            self.session.add(document)

        return job
