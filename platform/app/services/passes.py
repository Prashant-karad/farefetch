from datetime import datetime, timezone
from pathlib import Path

import jwt

from app.config import settings

ISSUER = "fairfetch-platform"
KEY_ID = "pass-v1"  # lets us rotate keys later without breaking old passes
_PRIVATE_KEY = Path(settings.pass_private_key_path).read_text()


def issue_pass(
    *, agent_id: str, grant_id: str, resource_id: str, path: str, license_id: str, expires_at: datetime
) -> str:
    """A signed, tamper-proof time pass. Anyone with the PUBLIC key can verify it; only we can create it."""
    claims = {
        "iss": ISSUER,              # who issued it
        "sub": agent_id,            # who it belongs to
        "jti": grant_id,            # unique ID (used for revocation)
        "rid": resource_id,
        "path": path,               # exactly which URL it unlocks
        "lic": license_id,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,          # verifiers reject it after this time
    }
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="ES256", headers={"kid": KEY_ID})