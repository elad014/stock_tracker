import base64
import binascii
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Final

from dotenv import load_dotenv
from joserfc import jwe, jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

load_dotenv()

ACCESS_TOKEN_TYPE: Final[str] = "access"
RESET_TOKEN_TYPE: Final[str] = "reset"

_KEY_BYTES: Final[int] = 32
_ALG: Final[str] = "dir"
_ENC: Final[str] = "A256GCM"
_MAX_TOKEN_CHARS: Final[int] = 4096

_HEADER: Final[dict[str, str]] = {"alg": _ALG, "enc": _ENC}
_REGISTRY: Final[jwe.JWERegistry] = jwe.JWERegistry(algorithms=[_ALG, _ENC])
_CLAIMS: Final[JWTClaimsRegistry] = JWTClaimsRegistry(
    exp={"essential": True},
    sub={"essential": True},
    type={"essential": True},
)


class TokenError(Exception):
    """Raised when a token cannot be decrypted, is expired, or fails claim validation."""


def _load_key() -> OctKey:
    encoded: str = os.getenv("JWT_SECRET_KEY", "").strip()
    if not encoded:
        raise RuntimeError("JWT_SECRET_KEY is not set")
    padded: str = encoded + "=" * (-len(encoded) % 4)
    try:
        secret: bytes = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("JWT_SECRET_KEY must be base64url-encoded") from exc
    if len(secret) != _KEY_BYTES:
        raise RuntimeError(f"JWT_SECRET_KEY must decode to {_KEY_BYTES} bytes for {_ENC}")
    return OctKey.import_key(secret)


_KEY: Final[OctKey] = _load_key()


def create_token(claims: dict[str, Any], expires_minutes: int) -> str:
    payload: dict[str, Any] = claims.copy()
    now: datetime = datetime.now(timezone.utc)
    payload["iat"] = now
    payload["exp"] = now + timedelta(minutes=expires_minutes)
    return jwt.encode(_HEADER, payload, _KEY, registry=_REGISTRY)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    if not token or len(token) > _MAX_TOKEN_CHARS:
        raise TokenError("Malformed token")
    try:
        decoded = jwt.decode(token, _KEY, registry=_REGISTRY)
        _CLAIMS.validate(decoded.claims)
    except (JoseError, ValueError, TypeError) as exc:
        raise TokenError("Invalid or expired token") from exc
    if decoded.claims.get("type") != expected_type:
        raise TokenError("Invalid token type")
    return decoded.claims
