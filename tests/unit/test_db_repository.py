from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import ProcessingJob, ScrubbedDocument
from app.db.repositories.job_repository import ProcessingJobRepository
from app.services.document_processing_service import DocumentProcessingService


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


def _safe_batch() -> dict[str, object]:
    return {
        "job_type": "document_scan",
        "safe_to_send": True,
        "status": "success",
        "success_count": 1,
        "failed_count": 0,
        "combined_output": "=== good.txt ===\nJane Doe",
        "processed_files": [
            {
                "file_name": "good.txt",
                "status": "success",
                "safe_to_send": True,
                "redacted_count": 1,
                "warnings": [],
                "scrubbed_output": "Jane Doe",
            }
        ],
        "failed_files": [],
    }


def test_repository_persists_only_safe_batches() -> None:
    session = _make_session()
    repository = ProcessingJobRepository(session)

    safe_batch = _safe_batch()
    job = repository.persist_successful_batch("document_scan", safe_batch)

    assert job.safe_to_send is True
    assert job.failed_count == 0
    assert session.query(ProcessingJob).count() == 1
    assert session.query(ScrubbedDocument).count() == 1
    assert session.query(ScrubbedDocument).one().scrubbed_output == "Jane Doe"


def test_persistence_service_rejects_arbitrary_dictionary() -> None:
    session = _make_session()
    service = DocumentProcessingService("./synthetic")
    fabricated = {
        "job_type": "document_scan",
        "safe_to_send": True,
        "status": "success",
        "success_count": 1,
        "failed_count": 0,
        "combined_output": "=== good.txt ===\nJane Doe",
        "processed_files": [
            {
                "file_name": "good.txt",
                "status": "success",
                "safe_to_send": True,
                "redacted_count": 1,
                "warnings": [],
                "scrubbed_output": "Jane Doe",
            }
        ],
        "failed_files": [],
    }

    try:
        service.persist_batch_result(fabricated, session)
        raise AssertionError("arbitrary dictionary should be rejected")
    except TypeError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_persistence_service_accepts_trusted_pipeline_result() -> None:
    session = _make_session()
    service = DocumentProcessingService("./synthetic")
    trusted = service._create_trusted_batch_result(_safe_batch())

    job = service.persist_batch_result(trusted, session)

    assert job.safe_to_send is True
    assert session.query(ProcessingJob).count() == 1
    assert session.query(ScrubbedDocument).count() == 1


def test_repository_rejects_batch_with_non_empty_failed_files() -> None:
    session = _make_session()
    repository = ProcessingJobRepository(session)

    batch = _safe_batch()
    batch["failed_count"] = 0
    batch["failed_files"] = [{"file": "bad.txt", "reason": "Extraction failed."}]

    try:
        repository.persist_successful_batch("document_scan", batch)
        raise AssertionError("batch with failed_files should be rejected")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_repository_rejects_success_count_mismatch() -> None:
    session = _make_session()
    repository = ProcessingJobRepository(session)

    batch = _safe_batch()
    batch["success_count"] = 2

    try:
        repository.persist_successful_batch("document_scan", batch)
        raise AssertionError("success count mismatch should be rejected")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_repository_rejects_malformed_batch_data() -> None:
    session = _make_session()
    repository = ProcessingJobRepository(session)

    malformed_batch = {
        "job_type": "document_scan",
        "safe_to_send": True,
        "status": "success",
        "success_count": "1",
        "failed_count": 0,
        "combined_output": "=== good.txt ===\nJane Doe",
        "processed_files": [
            {
                "file_name": "good.txt",
                "status": "success",
                "safe_to_send": True,
                "redacted_count": 1,
                "warnings": [],
                "scrubbed_output": "Jane Doe",
            }
        ],
        "failed_files": [],
    }

    try:
        repository.persist_successful_batch("document_scan", malformed_batch)
        raise AssertionError("malformed batch should be rejected")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_repository_rejects_unsafe_or_partial_batches() -> None:
    session = _make_session()
    repository = ProcessingJobRepository(session)

    unsafe_batch = {
        "job_type": "document_scan",
        "safe_to_send": False,
        "status": "unsafe_batch",
        "success_count": 1,
        "failed_count": 1,
        "combined_output": "=== good.txt ===\nJane Doe",
        "processed_files": [
            {
                "file_name": "good.txt",
                "status": "success",
                "safe_to_send": True,
                "redacted_count": 1,
                "warnings": [],
                "scrubbed_output": "Jane Doe",
            }
        ],
        "failed_files": [{"file": "bad.txt", "reason": "Extraction failed."}],
    }

    try:
        repository.persist_successful_batch("document_scan", unsafe_batch)
        raise AssertionError("unsafe batch should not be persisted")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_service_persistence_boundary_rejects_unsafe_data() -> None:
    session = _make_session()
    service = DocumentProcessingService("./synthetic")

    unsafe_batch = {
        "job_type": "document_scan",
        "safe_to_send": False,
        "status": "unsafe_batch",
        "success_count": 0,
        "failed_count": 1,
        "combined_output": "",
        "processed_files": [],
        "failed_files": [{"file": "bad.txt", "reason": "Extraction failed."}],
    }

    try:
        service._create_trusted_batch_result(unsafe_batch)
        raise AssertionError("unsafe batch should fail before persistence")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_commit_failure_triggers_rollback(monkeypatch) -> None:
    session = _make_session()
    service = DocumentProcessingService("./synthetic")
    trusted_batch = service._create_trusted_batch_result(_safe_batch())

    def raise_on_commit() -> None:
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(session, "commit", raise_on_commit)

    try:
        service.persist_batch_result(trusted_batch, session)
        raise AssertionError("commit failure should trigger rollback")
    except RuntimeError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0


def test_failed_batch_leaves_no_successful_job_or_document_records() -> None:
    session = _make_session()
    service = DocumentProcessingService("./synthetic")
    failed_batch = {
        "job_type": "document_scan",
        "safe_to_send": False,
        "status": "unsafe_batch",
        "success_count": 1,
        "failed_count": 1,
        "combined_output": "=== good.txt ===\nJane Doe",
        "processed_files": [
            {
                "file_name": "good.txt",
                "status": "success",
                "safe_to_send": True,
                "redacted_count": 1,
                "warnings": [],
                "scrubbed_output": "Jane Doe",
            }
        ],
        "failed_files": [{"file": "bad.txt", "reason": "Extraction failed."}],
    }

    try:
        service._create_trusted_batch_result(failed_batch)
        raise AssertionError("failed batch should not be trusted for persistence")
    except ValueError:
        pass

    assert session.query(ProcessingJob).count() == 0
    assert session.query(ScrubbedDocument).count() == 0
