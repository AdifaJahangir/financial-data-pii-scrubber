
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Financial Data PII Scrubber"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str | None = None
    db_echo: bool = False

    log_level: str = "INFO"
    allowed_file_types: str = ".pdf,.docx,.csv,.txt"
    max_upload_size_mb: int = 10
    local_processing_directory: str = "./data"

    # Groq configuration
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_api_base_url: str = "https://api.groq.com/openai/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
