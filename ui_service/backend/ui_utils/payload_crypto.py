import base64
import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_RSA_KEY_SIZE: int = 2048
_AES_KEY_BITS: int = 256
_GCM_IV_BYTES: int = 12
_MAX_WRAPPED_KEY_BYTES: int = 512
_MAX_CIPHERTEXT_BYTES: int = 4096
_OAEP: padding.OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def _load_or_create_private_key() -> RSAPrivateKey:
    pem_text: str = os.getenv("LOGIN_PAYLOAD_PRIVATE_KEY", "").strip()
    if not pem_text:
        return rsa.generate_private_key(public_exponent=65537, key_size=_RSA_KEY_SIZE)
    pem_text = pem_text.replace("\\n", "\n")
    loaded: object = serialization.load_pem_private_key(
        pem_text.encode("utf-8"),
        password=None,
    )
    if not isinstance(loaded, RSAPrivateKey):
        raise ValueError("LOGIN_PAYLOAD_PRIVATE_KEY must be an RSA private key")
    return loaded


_PRIVATE_KEY: RSAPrivateKey = _load_or_create_private_key()


def _b64url_uint(value: int) -> str:
    length: int = (value.bit_length() + 7) // 8
    raw: bytes = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def public_jwk() -> dict[str, str]:
    numbers = _PRIVATE_KEY.public_key().public_numbers()
    return {
        "kty": "RSA",
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }


def _b64decode(value: str, max_bytes: int) -> bytes:
    try:
        raw: bytes = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("Invalid encrypted payload") from exc
    if not raw or len(raw) > max_bytes:
        raise ValueError("Invalid encrypted payload")
    return raw


def encrypt_json(payload: dict[str, Any]) -> dict[str, str]:
    raw: bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    aes_key: bytes = AESGCM.generate_key(bit_length=_AES_KEY_BITS)
    nonce: bytes = os.urandom(_GCM_IV_BYTES)
    ciphertext: bytes = AESGCM(aes_key).encrypt(nonce, raw, None)
    wrapped: bytes = _PRIVATE_KEY.public_key().encrypt(aes_key, _OAEP)
    return {
        "wrapped_key": base64.b64encode(wrapped).decode("ascii"),
        "iv": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_json(wrapped_key: str, iv: str, ciphertext: str) -> dict[str, Any]:
    wrapped: bytes = _b64decode(wrapped_key, _MAX_WRAPPED_KEY_BYTES)
    nonce: bytes = _b64decode(iv, _GCM_IV_BYTES)
    if len(nonce) != _GCM_IV_BYTES:
        raise ValueError("Invalid encrypted payload")
    blob: bytes = _b64decode(ciphertext, _MAX_CIPHERTEXT_BYTES)
    try:
        aes_key: bytes = _PRIVATE_KEY.decrypt(wrapped, _OAEP)
        plain: bytes = AESGCM(aes_key).decrypt(nonce, blob, None)
        parsed: object = json.loads(plain.decode("utf-8"))
    except (ValueError, InvalidTag, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid encrypted payload") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Invalid encrypted payload")
    return parsed
