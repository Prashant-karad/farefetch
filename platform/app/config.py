from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file).

    There are deliberately no defaults for connection strings:
    if a required setting is missing, the app fails at startup
    instead of quietly connecting to the wrong place.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),  # repo root first, then current folder
        extra="ignore",
    )

    database_url: str
    redis_url: str
    environment: str = "development"


settings = Settings()
