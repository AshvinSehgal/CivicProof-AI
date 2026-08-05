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
    nws_base_url: str = "https://api.weather.gov"
    nws_timeout_seconds: float = 5.0
    nws_cache_ttl_seconds: float = 300.0

@lru_cache
def get_settings() -> Settings:
    return Settings()
