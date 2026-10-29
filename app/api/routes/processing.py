
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.document_processing_service import (
    DocumentProcessingService,
)

settings = get_settings()

router = APIRouter(tags=["processing"])


@router.post("/process-local")
async def process_local() -> dict[str, object]:
    configured_dir = (
        Path(settings.local_processing_directory)
        .expanduser()
        .resolve()
    )

    # Temporary diagnostics
   

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

    all_files = sorted(
        item for item in configured_dir.rglob("*") if item.is_file()
    )

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
        resolved = file_path.resolve()

        try:
            resolved.relative_to(configured_dir)
        except ValueError:
            failed_files.append({
                "file": file_path.name,
                "reason": "File rejected: path outside the configured directory.",
            })
            continue

        if file_path.suffix.lower() not in {
            ".pdf", ".docx", ".csv", ".txt"
        }:
            failed_files.append({
                "file": file_path.name,
                "reason": "File rejected: unsupported extension.",
            })
            continue

        try:
            if file_path.stat().st_size > max_bytes:
                failed_files.append({
                    "file": file_path.name,
                    "reason": "File rejected: exceeds configured size limit.",
                })
                continue
        except OSError:
            failed_files.append({
                "file": file_path.name,
                "reason": "File rejected: unreadable file.",
            })
            continue

        supported_files.append(file_path)

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

    batch_result = service.process_directory()

    if not isinstance(batch_result, dict):
        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "Processing pipeline returned an invalid result.",
            "job_id": None,
            "failed_files": [],
        }

    if (
        batch_result.get("safe_to_send") is not True
        or batch_result.get("status") != "success"
    ):
        sanitized_failed_files = [
            {
                "file": item.get("file", "unknown"),
                "reason": item.get("reason", "Processing failed."),
            }
            for item in batch_result.get("failed_files", [])
            if isinstance(item, dict)
        ]

        return {
            "status": "unsafe",
            "safe_to_send": False,
            "processed_count": batch_result.get("success_count", 0),
            "failed_count": batch_result.get("failed_count", 0),
            "reason": "Batch did not pass the local safety checks.",
            "job_id": None,
            "failed_files": sanitized_failed_files,
        }

    trusted_batch = service._create_trusted_batch_result(batch_result)
    session = None

    try:
        session = SessionLocal()
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

    except RuntimeError as exc:
        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": str(exc),
            "job_id": None,
            "failed_files": [],
        }

    except Exception:
        if session is not None:
            session.rollback()

        return {
            "status": "error",
            "safe_to_send": False,
            "processed_count": 0,
            "failed_count": 0,
            "reason": "Batch failed persistence validation.",
            "job_id": None,
            "failed_files": [],
        }

    finally:
        if session is not None:
            session.close()
