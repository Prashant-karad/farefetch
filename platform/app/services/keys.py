"""Load the ES256 private signing key from an env var (PEM text) or a file path."""

from pathlib import Path

from app.config import settings


def load_private_key() -> str:
    if settings.pass_private_key:
        # Env vars often store newlines as literal "\n"
        return settings.pass_private_key.replace("\\n", "\n")
    if settings.pass_private_key_path:
        return Path(settings.pass_private_key_path).read_text()
    raise RuntimeError("Set PASS_PRIVATE_KEY (PEM text) or PASS_PRIVATE_KEY_PATH")


PRIVATE_KEY = load_private_key()
