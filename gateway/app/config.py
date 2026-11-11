from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    redis_url: str
    internal_token: str
    platform_url: str                       # how the gateway reaches the platform
    public_platform_url: str | None = None  # what agents are told in the 402 (defaults to platform_url)
    origin_url: str
    pass_public_key: str | None = None       # PEM text (hosting) ...
    pass_public_key_path: str | None = None  # ... or a file path (local dev)
    resource_cache_seconds: int = 60
    agent_cache_seconds: int = 60


settings = Settings()

for _name in ("platform_url", "origin_url"):
    if "://" not in getattr(settings, _name):
        setattr(settings, _name, "http://" + getattr(settings, _name))
