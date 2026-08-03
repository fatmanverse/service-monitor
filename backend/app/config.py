from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./service_monitor.db"
    app_secret: str = "change-this-service-monitor-secret"
    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin123"
    access_token_minutes: int = 480
    scheduler_enabled: bool = True
    monitor_workers: int = 200
    testing: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
