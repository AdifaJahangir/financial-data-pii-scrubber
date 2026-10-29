
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


class SessionFactory:
    def __init__(self) -> None:
        self._session_factory = None
        self._database_url: str | None = None
        self._engine = None

    def _ensure_session_factory(self):
        settings = get_settings()

        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured. "
                "Set it in the environment or .env before using the database layer."
            )

        if (
            self._session_factory is None
            or self._database_url != settings.database_url
        ):
            if self._engine is not None:
                self._engine.dispose()

            self._engine = create_engine(
                settings.database_url,
                pool_pre_ping=True,
                echo=settings.db_echo,
            )

            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

            self._database_url = settings.database_url

        return self._session_factory

    def __call__(self, *args, **kwargs):
        return self._ensure_session_factory()(*args, **kwargs)


SessionLocal = SessionFactory()
