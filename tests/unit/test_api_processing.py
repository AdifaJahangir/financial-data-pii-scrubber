from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.config import get_settings
from app.main import app
import app.api.routes.processing as processing_routes


client = TestClient(app)


def _override_db() -> object:
    return object()


def _set_processing_dir(monkeypatch, tmp_path, *, max_upload_size_mb: int = 10) -> None:
    monkeypatch.setattr(processing_routes.settings, "local_processing_directory", str(tmp_path))
    monkeypatch.setattr(processing_routes.settings, "max_upload_size_mb", max_upload_size_mb)
    app.dependency_overrides[get_db] = _override_db


def test_health_endpoint_works_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_process_local_success_returns_sanitized_metadata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "statement.txt").write_text(
        "Customer: Jane Doe\nAccount: 1234567890\nAmount: $150.00\n",
        encoding="utf-8",
    )
    _set_processing_dir(monkeypatch, data_dir)

    mock_job = SimpleNamespace(id=42)
    persisted = MagicMock(return_value=mock_job)

    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["safe_to_send"] is True
    assert payload["processed_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["job_id"] == 42
    assert "Jane Doe" not in str(payload)
    assert "1234567890" not in str(payload)
    assert "statement.txt" not in str(payload)
    persisted.assert_called_once()


def test_process_local_returns_clear_error_when_database_is_missing(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "statement.txt").write_text("Customer: Jane Doe\nAmount: $50.00\n", encoding="utf-8")
    _set_processing_dir(monkeypatch, data_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(
    "app.db.session.get_settings",
    lambda: SimpleNamespace(database_url=None, db_echo=False),
)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["safe_to_send"] is False
    assert "DATABASE_URL is not configured" in payload["reason"]


def test_process_local_unsafe_batch_does_not_persist(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "good.txt").write_text("Customer: Jane Doe\nAmount: $10.00\n", encoding="utf-8")
    (data_dir / "bad.txt").write_text("", encoding="utf-8")
    _set_processing_dir(monkeypatch, data_dir)

    persisted = MagicMock(return_value=SimpleNamespace(id=99))
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsafe"
    assert payload["safe_to_send"] is False
    assert payload["failed_count"] >= 1
    assert payload["job_id"] is None
    assert "Jane Doe" not in str(payload)
    persisted.assert_not_called()


def test_process_local_rejects_unsupported_files(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "statement.txt").write_text("Customer: Jane Doe\nAmount: $50.00\n", encoding="utf-8")
    (data_dir / "notes.md").write_text("not allowed", encoding="utf-8")
    _set_processing_dir(monkeypatch, data_dir)

    persisted = MagicMock(return_value=SimpleNamespace(id=7))
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsafe"
    assert payload["safe_to_send"] is False
    assert payload["failed_count"] == 1
    assert any(item["reason"] == "File rejected: unsupported extension." for item in payload["failed_files"])
    persisted.assert_not_called()


def test_process_local_rejects_unsafe_configured_path(monkeypatch, tmp_path) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    _set_processing_dir(monkeypatch, outside_dir)

    persisted = MagicMock(return_value=SimpleNamespace(id=11))
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsafe"
    assert payload["safe_to_send"] is False
    assert payload["job_id"] is None
    persisted.assert_not_called()


def test_process_local_rejects_oversized_files(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "large.txt").write_text("x" * 1024, encoding="utf-8")
    _set_processing_dir(monkeypatch, data_dir, max_upload_size_mb=0)

    persisted = MagicMock(return_value=SimpleNamespace(id=13))
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsafe"
    assert payload["safe_to_send"] is False
    assert any(item["reason"] == "File rejected: exceeds configured size limit." for item in payload["failed_files"])
    persisted.assert_not_called()


def test_process_local_response_is_sanitized_and_does_not_return_raw_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    get_settings.cache_clear()

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "statement.txt").write_text(
        "Customer: Jane Doe\nEmail: jane@example.com\nPhone: +1 415-555-0182\n",
        encoding="utf-8",
    )
    _set_processing_dir(monkeypatch, data_dir)

    mock_job = SimpleNamespace(id=21)
    persisted = MagicMock(return_value=mock_job)
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert "jane@example.com" not in str(payload)
    assert "415-555-0182" not in str(payload)
    assert "Jane Doe" not in str(payload)
    assert "absolute" not in str(payload).lower()


def test_process_local_rejects_symlink_escape(monkeypatch, tmp_path) -> None:
    permitted_dir = tmp_path / "permitted"
    permitted_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "outside.txt"
    outside_file.write_text("Customer: Jane Doe\nAccount: 1234567890\n", encoding="utf-8")

    link_path = permitted_dir / "linked.txt"
    try:
        link_path.symlink_to(outside_file)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("Symlink creation is unavailable or blocked on this platform.")

    _set_processing_dir(monkeypatch, permitted_dir)

    persisted = MagicMock(return_value=SimpleNamespace(id=99))
    monkeypatch.setattr("app.services.document_processing_service.DocumentProcessingService.persist_batch_result", persisted)

    response = client.post("/api/v1/process-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsafe"
    assert payload["safe_to_send"] is False
    assert payload["job_id"] is None
    persisted.assert_not_called()

def test_upload_success_with_synthetic_txt(monkeypatch):
    app.dependency_overrides[get_db] = _override_db

    def fake_persist(self, trusted_batch, db):
        return SimpleNamespace(id=123)

    monkeypatch.setattr(
        processing_routes.DocumentProcessingService,
        "persist_batch_result",
        fake_persist,
    )

    response = client.post(
        "/api/v1/upload",
        files=[
            (
                "files",
                (
                    "synthetic_statement.txt",
                    b"Account Number: 123456789012\nMerchant: Example Store\nAmount: PKR 2500",
                    "text/plain",
                ),
            )
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["safe_to_send"] is True
    assert result["job_id"] == 123
    assert result["processed_count"] == 1
    assert "123456789012" not in result["combined_output"]

def test_upload_processes_multiple_synthetic_files(monkeypatch):
    app.dependency_overrides[get_db] = _override_db

    def fake_persist(self, trusted_batch, db):
        return SimpleNamespace(id=456)

    monkeypatch.setattr(
        processing_routes.DocumentProcessingService,
        "persist_batch_result",
        fake_persist,
    )

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("first.txt", b"Merchant: Alpha Store\nAmount: PKR 500", "text/plain")),
            ("files", ("second.csv", b"DATE,DESCRIPTION,AMOUNT\n2026-01-01,Beta Store,1200", "text/csv")),
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["processed_count"] == 2
    assert result["job_id"] == 456
    assert "first.txt" in result["combined_output"]
    assert "second.csv" in result["combined_output"]

def test_upload_rejects_unsupported_extension():
    app.dependency_overrides[get_db] = _override_db

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("malware.exe", b"synthetic content", "application/octet-stream"))
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Only PDF, DOCX, CSV and TXT" in response.json()["detail"]

def test_upload_rejects_empty_file():
    app.dependency_overrides[get_db] = _override_db

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("empty.txt", b"", "text/plain"))
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Empty files are not accepted." in response.json()["detail"]

def test_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(processing_routes.settings, "max_upload_size_mb", 1)
    app.dependency_overrides[get_db] = _override_db

    large_content = b"A" * (1024 * 1024 + 1)

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("large.txt", large_content, "text/plain"))
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "exceeds the configured size limit" in response.json()["detail"]

def test_upload_rejects_duplicate_filenames():
    app.dependency_overrides[get_db] = _override_db

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("statement.txt", b"Merchant: Alpha", "text/plain")),
            ("files", ("statement.txt", b"Merchant: Beta", "text/plain")),
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Duplicate filenames are not allowed." in response.json()["detail"]

def test_upload_rejects_path_traversal_filename():
    app.dependency_overrides[get_db] = _override_db

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("..\\secret.txt", b"synthetic content", "text/plain")),
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "uploaded filename is invalid" in response.json()["detail"]

def test_upload_unsafe_batch_is_not_persisted(monkeypatch):
    app.dependency_overrides[get_db] = _override_db
    persist_mock = MagicMock()

    monkeypatch.setattr(
        processing_routes.DocumentProcessingService,
        "persist_batch_result",
        persist_mock,
    )

    monkeypatch.setattr(
        processing_routes.DocumentProcessingService,
        "process_directory",
        lambda self, *args, **kwargs: {
            "status": "unsafe",
            "safe_to_send": False,
            "failed_count": 1,
            "failed_files": [{"file": "synthetic.txt", "reason": "synthetic failure"}],
        },
    )

    response = client.post(
        "/api/v1/upload",
        files=[
            ("files", ("synthetic.txt", b"synthetic test content", "text/plain")),
        ],
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "unsafe"
    assert response.json()["safe_to_send"] is False
    assert response.json()["combined_output"] is None
    persist_mock.assert_not_called()
