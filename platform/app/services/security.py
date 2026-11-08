import hashlib
import secrets

API_KEY_PREFIX = "ffk_"


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, lookup_prefix, hash). Show full_key to the user ONCE; store only prefix + hash."""
    full_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return full_key, full_key[:12], hash_api_key(full_key)
