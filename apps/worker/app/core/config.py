from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    APP_ENV: str = "production"
    DATABASE_URL: str = "postgresql://mediaapp:mediaapp_change_me_secret_pass@postgres:5432/mediaapp"
    REDIS_URL: str = "redis://redis:6379/0"

    MEDIA_ROOT: str = "/downloads"
    STAGING_DIR: str = "/staging"
    MAX_CONCURRENT_JOBS: int = 1
    LOG_LEVEL: str = "INFO"
    ENABLE_YOUTUBE_DOWNLOAD: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


worker_settings = WorkerSettings()
settings = worker_settings
