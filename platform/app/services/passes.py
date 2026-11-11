from datetime import datetime, timezone

import jwt

from app.services.keys import PRIVATE_KEY

ISSUER = "fairfetch-platform"
KEY_ID = "pass-v1"  # lets us rotate keys later without breaking old passes


def issue_pass(
    *, agent_id: str, grant_id: str, resource_id: str, path: str, license_id: str, expires_at: datetime
) -> str:
    """A signed, tamper-proof time pass. Anyone with the PUBLIC key can verify it; only we can create it."""
    claims = {
        "iss": ISSUER,
        "sub": agent_id,
        "jti": grant_id,
        "rid": resource_id,
        "path": path,
        "lic": license_id,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="ES256", headers={"kid": KEY_ID})


def sign_receipt(payload: dict) -> str:
    """Usage receipts are signed with the same key so publishers can verify them with the public key."""
    claims = {"iss": ISSUER, "typ": "usage_receipt", "iat": datetime.now(timezone.utc), **payload}
    return jwt.encode(claims, PRIVATE_KEY, algorithm="ES256", headers={"kid": KEY_ID})
