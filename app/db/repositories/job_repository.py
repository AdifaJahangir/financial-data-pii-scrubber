from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ProcessingJob, ScrubbedDocument


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def _validate_success_batch(self, batch_result: dict[str, object]) -> None:
        if not isinstance(batch_result, dict):
            raise ValueError("Batch result must be a dictionary.")

        if not isinstance(batch_result.get("job_type"), str) or not batch_result.get("job_type", "").strip():
            raise ValueError("Batch job type is required and must be a non-empty string.")

        safe_to_send = batch_result.get("safe_to_send")
        status = batch_result.get("status")
        failed_count = batch_result.get("failed_count")
        success_count = batch_result.get("success_count")
        failed_files = batch_result.get("failed_files")
        processed_files = batch_result.get("processed_files")
        combined_output = batch_result.get("combined_output")

        if safe_to_send is not True:
            raise ValueError("Batch is not safe to send and cannot be persisted as successful.")
        if status != "success":
            raise ValueError("Successful batch status mismatch.")
        if not isinstance(failed_count, int) or failed_count != 0:
            raise ValueError("Failed files are present; batch cannot be persisted as successful.")
        if not isinstance(failed_files, list) or failed_files != []:
            raise ValueError("Failed file list must be empty for a successful batch.")
        if not isinstance(success_count, int) or success_count <= 0:
            raise ValueError("Successful batch must include at least one processed file.")
        if not isinstance(processed_files, list) or not processed_files:
            raise ValueError("No processed files were available for persistence.")
        if success_count != len(processed_files):
            raise ValueError("Success count does not match the number of processed files.")
        if not isinstance(combined_output, str) or not combined_output.strip():
            raise ValueError("Combined output is empty; batch cannot be persisted.")

        for item in processed_files:
            if not isinstance(item, dict):
                raise ValueError("Processed file metadata is invalid.")
            if item.get("status") != "success":
                raise ValueError("A processed file was not marked successful.")
            if item.get("safe_to_send") is not True:
                raise ValueError("A processed file was not safe to persist.")
            if not isinstance(item.get("file_name"), str) or not item["file_name"].strip():
                raise ValueError("A processed file is missing a valid file name.")
            if not isinstance(item.get("redacted_count"), int) or item["redacted_count"] < 0:
                raise ValueError("A processed file has an invalid redaction count.")
            warnings = item.get("warnings")
            if warnings is not None and not isinstance(warnings, list):
                raise ValueError("A processed file has malformed warnings metadata.")
            scrubbed_output = item.get("scrubbed_output")
            if not isinstance(scrubbed_output, str) or not scrubbed_output.strip():
                raise ValueError("A processed file has empty scrubbed output.")

    def persist_successful_batch(self, job_type: str, batch_result: dict[str, object]) -> ProcessingJob:
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("Job type must be a non-empty string.")
        if not isinstance(batch_result, dict):
            raise ValueError("Batch result must be a dictionary.")

        self._validate_success_batch({**batch_result, "job_type": job_type})

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
