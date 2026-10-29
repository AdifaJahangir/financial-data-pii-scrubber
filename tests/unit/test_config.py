
from __future__ import annotations

import importlib

import pytest

from app.core.config import get_settings


def test_database_url_reads_from_environment(monkeypatch) -> None:
    expected_url = (
        "postgresql+psycopg://example_user:example_pass@db.example:5432/example_db"
    )
    monkeypatch.setenv("DATABASE_URL", expected_url)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == expected_url
    assert settings.db_echo is False


def test_missing_database_url_raises_clear_error(monkeypatch, tmp_path) -> None:
    # Run outside the project directory so the real .env file is not loaded.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.database_url is None

    import app.db.session as session_module

    importlib.reload(session_module)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        session_module.SessionLocal()

    get_settings.cache_clear()
