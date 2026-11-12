from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file).
    No defaults for connection strings or secrets: missing config fails at startup."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    redis_url: str
    internal_token: str
    environment: str = "development"

    # Pass/receipt signing key: PEM text (for hosting) OR a file path (for local dev).
    pass_private_key: str | None = None
    pass_private_key_path: str | None = None

    # PayPal (sandbox by default, so a missing setting can never hit live money)
    paypal_client_id: str
    paypal_client_secret: str
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    public_base_url: str

    # Where the publisher's origin lives (the license guard fetches source text from it)
    origin_url: str = "http://127.0.0.1:8002"

    # Live story page (/live): runs the seeded demo agent. Turn off for anything real.
    demo_mode: bool = True
    demo_agent_api_key: str | None = None
    gateway_url: str = "http://127.0.0.1:8000"
    edge_proxy_gateway: bool = False
    # Sandbox buyer shown to visitors in test mode so anyone can try PayPal Checkout (sandbox money only)
    paypal_test_buyer_email: str | None = None
    paypal_test_buyer_password: str | None = None   # single-host deploy: serve the gateway's public paths too

    # LLM (optional: without a key, deterministic fallbacks are used)
    llm_provider: str = "groq"           # "groq" or "gemini"
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_model: str | None = None         # default chosen per provider in services/llm.py


settings = Settings()

# Some hosts (Render) give postgres://... URLs; SQLAlchemy async needs postgresql+asyncpg://
if settings.database_url.startswith("postgres://"):
    settings.database_url = settings.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif settings.database_url.startswith("postgresql://"):
    settings.database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Hosts may give "host:port" for private addresses; make sure URLs have a scheme.
if "://" not in settings.origin_url:
    settings.origin_url = "http://" + settings.origin_url
