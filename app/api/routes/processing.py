
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.document_processing_service import (
    DocumentProcessingService,
)

settings = get_settings()

router = APIRouter(tags=["processing"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".txt"}
CHUNK_SIZE = 1024 * 1024
MAX_FILES_PER_REQUEST = 20
MAX_TOTAL_UPLOAD_SIZE_MB = 50


@router.post("/process-local")
async def process_local() -> dict[str, object]:
    configured_dir = (
        Path(settings.local_processing_directory)
        .expanduser()
        .resolve()
    )

    if not configured_dir.is_dir():
        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "Configured processing directory is unavailable.",
            "job_id": None,
            "failed_files": [],
        }

    service = DocumentProcessingService(configured_dir)

    try:
        all_files = sorted(
            item
            for item in configured_dir.rglob("*")
            if item.is_file()
        )
    except OSError:
        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "Unable to inspect configured directory.",
            "job_id": None,
            "failed_files": [],
        }

    if not all_files:
        return {
            "status": "unsafe",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "No files were found in the configured directory.",
            "job_id": None,
            "failed_files": [],
        }

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    supported_files: list[Path] = []
    failed_files: list[dict[str, str]] = []

    for file_path in all_files:
        try:
            resolved = file_path.resolve(strict=True)
            resolved.relative_to(configured_dir)

            if not resolved.is_file():
                raise ValueError("Not a regular file.")

            if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
                failed_files.append({
                    "file": file_path.name,
                    "reason": "File rejected: unsupported extension.",
                })
                continue

            if resolved.stat().st_size > max_bytes:
                failed_files.append({
                    "file": file_path.name,
                    "reason": "File rejected: exceeds configured size limit.",
                })
                continue

            supported_files.append(resolved)

        except (OSError, ValueError):
            failed_files.append({
                "file": file_path.name,
                "reason": "File rejected: path or accessibility validation failed.",
            })

    if failed_files:
        return {
            "status": "unsafe",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": len(failed_files),
            "reason": "One or more files failed validation before extraction.",
            "job_id": None,
            "failed_files": failed_files,
        }

    if not supported_files:
        return {
            "status": "unsafe",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "No eligible files remained after validation.",
            "job_id": None,
            "failed_files": [],
        }

    try:
        batch_result = service.process_directory(
            supported_files,
            max_file_size_bytes=max_bytes,
        )

        if not isinstance(batch_result, dict):
            raise ValueError("Invalid processing result.")

        if (
            batch_result.get("safe_to_send") is not True
            or batch_result.get("status") != "success"
        ):
            raw_failed_files = batch_result.get("failed_files", [])

            sanitized_failed_files = (
                [
                    {
                        "file": item.get("file", "unknown"),
                        "reason": "File failed extraction or safety validation.",
                    }
                    for item in raw_failed_files
                    if isinstance(item, dict)
                ]
                if isinstance(raw_failed_files, list)
                else []
            )

            return {
                "status": "unsafe",
                "safe_to_send": False,
                "processed_count": 0,
                "failed_count": batch_result.get("failed_count", 0),
                "reason": "Batch did not pass the local safety checks.",
                "job_id": None,
                "failed_files": sanitized_failed_files,
            }

        trusted_batch = service._create_trusted_batch_result(batch_result)

        session = SessionLocal()

        try:
            job = service.persist_batch_result(trusted_batch, session)

            return {
                "status": "success",
                "safe_to_send": True,
                "processed_count": trusted_batch.success_count,
                "failed_count": 0,
                "reason": "Batch passed validation and was persisted.",
                "job_id": job.id,
                "failed_files": [],
            }

        finally:
            session.close()

    except RuntimeError as exc:
        if "DATABASE_URL is not configured" in str(exc):
            reason = "DATABASE_URL is not configured."
        else:
            reason = "Database or processing operation failed."

        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": reason,
            "job_id": None,
            "failed_files": [],
        }

    except Exception:
        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "Batch failed processing or persistence validation.",
            "job_id": None,
            "failed_files": [],
        }


@router.post("/upload")
async def upload_and_process(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    max_total_bytes = MAX_TOTAL_UPLOAD_SIZE_MB * 1024 * 1024

    try:
        if max_bytes <= 0 or max_total_bytes <= 0:
            raise HTTPException(
                status_code=500,
                detail="The configured upload size limit is invalid.",
            )

        if not files:
            raise HTTPException(
                status_code=400,
                detail="Select at least one file.",
            )

        if len(files) > MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=400,
                detail=f"A maximum of {MAX_FILES_PER_REQUEST} files is allowed.",
            )

        filenames: list[str] = []
        seen_names: set[str] = set()

        for upload in files:
            filename = upload.filename

            if (
                not isinstance(filename, str)
                or not filename.strip()
                or filename in {".", ".."}
                or "/" in filename
                or "\\" in filename
                or "\x00" in filename
                or ":" in filename
                or len(filename) > 255
                or Path(filename).name != filename
            ):
                raise HTTPException(
                    status_code=400,
                    detail="An uploaded filename is invalid.",
                )

            if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF, DOCX, CSV and TXT files are supported.",
                )

            if filename in seen_names:
                raise HTTPException(
                    status_code=400,
                    detail="Duplicate filenames are not allowed.",
                )

            seen_names.add(filename)
            filenames.append(filename)

        with tempfile.TemporaryDirectory(
            prefix="financial-pii-upload-"
        ) as temporary_directory:
            temporary_root = Path(temporary_directory).resolve()
            saved_paths: list[Path] = []
            total_request_bytes = 0

            for upload, filename in zip(files, filenames):
                destination = temporary_root / filename
                file_bytes = 0

                try:
                    with destination.open("xb") as destination_file:
                        while True:
                            chunk = await upload.read(CHUNK_SIZE)

                            if not chunk:
                                break

                            file_bytes += len(chunk)
                            total_request_bytes += len(chunk)

                            if file_bytes > max_bytes:
                                raise HTTPException(
                                    status_code=413,
                                    detail="An uploaded file exceeds the configured size limit.",
                                )

                            if total_request_bytes > max_total_bytes:
                                raise HTTPException(
                                    status_code=413,
                                    detail="The total uploaded files exceed the 50 MB request limit.",
                                )

                            destination_file.write(chunk)

                except HTTPException:
                    raise
                except OSError:
                    raise HTTPException(
                        status_code=500,
                        detail="An uploaded file could not be stored temporarily.",
                    )

                if file_bytes == 0:
                    raise HTTPException(
                        status_code=400,
                        detail="Empty files are not accepted.",
                    )

                saved_paths.append(destination)

            service = DocumentProcessingService(temporary_root)

            batch_result = service.process_directory(
                saved_paths,
                max_file_size_bytes=max_bytes,
            )

            if not isinstance(batch_result, dict):
                raise ValueError("Invalid processing result.")

            if (
                batch_result.get("safe_to_send") is not True
                or batch_result.get("status") != "success"
            ):
                raw_failed_files = batch_result.get("failed_files", [])

                sanitized_failed_files = (
                    [
                        {
                            "file": item.get("file", "unknown"),
                            "reason": "File failed extraction or safety validation.",
                        }
                        for item in raw_failed_files
                        if isinstance(item, dict)
                    ]
                    if isinstance(raw_failed_files, list)
                    else []
                )

                return {
                    "status": "unsafe",
                    "safe_to_send": False,
                    "processed_count": 0,
                    "failed_count": batch_result.get("failed_count", 0),
                    "reason": "The uploaded batch did not pass local safety validation.",
                    "job_id": None,
                    "failed_files": sanitized_failed_files,
                    "combined_output": None,
                }

            trusted_batch = service._create_trusted_batch_result(batch_result)
            job = service.persist_batch_result(trusted_batch, db)

            return {
                "status": "success",
                "safe_to_send": True,
                "processed_count": trusted_batch.success_count,
                "failed_count": 0,
                "reason": "Uploaded files were scrubbed, validated and persisted.",
                "job_id": job.id,
                "failed_files": [],
                "combined_output": trusted_batch.combined_output,
                "processed_files": [
                    {
                        "file_name": item.file_name,
                        "redacted_count": item.redacted_count,
                        "status": item.status,
                        "safe_to_send": item.safe_to_send,
                    }
                    for item in trusted_batch.processed_files
                ],
            }

    except HTTPException:
        raise

    except RuntimeError as exc:
        if "DATABASE_URL is not configured" in str(exc):
            raise HTTPException(
                status_code=503,
                detail="DATABASE_URL is not configured.",
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="Database or processing operation failed.",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Upload processing or persistence validation failed.",
        ) from exc

    finally:
        for upload in files:
            try:
                await upload.close()
            except Exception:
                pass
