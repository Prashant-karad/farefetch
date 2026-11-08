from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file).
    No defaults for connection strings or secrets: missing config fails at startup."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    redis_url: str
    internal_token: str
    environment: str = "development"


settings = Settings()