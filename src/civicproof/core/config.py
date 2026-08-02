from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CIVICPROOF_",
        extra="ignore",
    )
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://civicproof:civicproof@localhost:5432/civicproof"
    redis_url: str = "redis://localhost:6379/0"
    nws_user_agent: str = "CivicProof/0.1 (local-development)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
