from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file).
    No defaults for connection strings or secrets: missing config fails at startup."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    redis_url: str
    internal_token: str
    pass_private_key_path: str
    paypal_client_id: str
    paypal_client_secret: str
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    public_base_url: str
    environment: str = "development"


settings = Settings()