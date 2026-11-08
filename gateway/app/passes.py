from pathlib import Path

import jwt

from app.config import settings

ISSUER = "fairfetch-platform"
_PUBLIC_KEY = Path(settings.pass_public_key_path).read_text()


class PassError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def verify_pass(token: str, *, agent_id: str, path: str) -> dict:
    """Prove the pass is genuine (signature) AND used correctly (claims). Returns the claims."""
    try:
        claims = jwt.decode(
            token,
            _PUBLIC_KEY,
            algorithms=["ES256"],          # accept ONLY this algorithm (blocks "alg: none" attacks)
            issuer=ISSUER,                 # must be issued by our platform
            options={"require": ["exp", "iat", "sub", "jti", "path"]},
            leeway=5,                      # tolerate 5s of clock difference between servers
        )
    except jwt.ExpiredSignatureError:
        raise PassError("pass_expired", "This pass has expired. Buy a new one.")
    except jwt.InvalidTokenError:
        raise PassError("invalid_pass", "Pass signature or format is invalid.")

    if claims["sub"] != agent_id:
        raise PassError("pass_not_yours", "This pass belongs to a different agent.")
    if claims["path"] != path:
        raise PassError("pass_wrong_resource", "This pass is for a different resource.")
    return claims