from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from naijaledger.db.connection import DEFAULT_DATABASE_URL


def load_settings() -> "Settings":
    return Settings()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ]
    )
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "changeme"
    minio_secret_key: str = "changeme"
    minio_bucket: str = "naijaledger-archive"
    minio_retention_days: int = 3650
    fetch_http_timeout: float = 60.0
    scrapling_timeout: float = 60.0
    scrapling_impersonate: str = "chrome"
    scrapling_stealthy_headers: bool = True
    playwright_timeout: float = 90.0
    playwright_headless: bool = True
    playwright_network_idle: bool = True
    playwright_post_wait_ms: int = 1000
    catalog_discovery_max_children: int = 50
    magika_min_confidence: float = 0.5
    ocr_max_pages: int = 20
    vision_llm_enabled: bool = False
    job_lock_timeout_seconds: int = 1800
    job_max_attempts: int = 3

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
