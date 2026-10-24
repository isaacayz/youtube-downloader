from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "production"
    APP_PORT: int = 8000
    DATABASE_URL: str = "postgresql://mediaapp:mediaapp_change_me_secret_pass@postgres:5432/mediaapp"
    REDIS_URL: str = "redis://redis:6379/0"

    MEDIA_ROOT: str = "/downloads"
    STAGING_DIR: str = "/staging"

    MAX_CONCURRENT_JOBS: int = 1
    MAX_UPLOAD_BYTES: int = 2147483648  # 2 GB
    MAX_OUTPUT_BYTES: int = 5368709120  # 5 GB
    MAX_JOB_DURATION_SECONDS: int = 3600
    MAX_REDIRECTS: int = 3
    JOB_RETRY_MAX: int = 3

    OUTPUT_RETENTION_DAYS: int = 7
    EVENT_RETENTION_DAYS: int = 30
    LOG_LEVEL: str = "INFO"

    ALLOWED_ORIGINS: str = "http://localhost:3000"
    PUBLIC_BASE_URL: str = "http://localhost:3000"
    ENABLE_LAN_ACCESS: bool = False
    ENABLE_YOUTUBE_DOWNLOAD: bool = False

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
