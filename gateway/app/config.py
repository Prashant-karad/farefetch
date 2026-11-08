from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    redis_url: str
    internal_token: str
    platform_url: str
    origin_url: str
    pass_public_key_path: str
    resource_cache_seconds: int = 60
    agent_cache_seconds: int = 60


settings = Settings()