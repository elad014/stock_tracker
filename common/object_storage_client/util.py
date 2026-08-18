import mimetypes
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from constant import S3_DEFAULT_CONTENT_TYPE, S3_FOLDER_PLACEHOLDER


class ObjectStorageError(RuntimeError):
    """Raised when an object storage operation fails or is misconfigured."""


@dataclass
class StoredObject:
    key: str
    size: Optional[int] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None
    last_modified: Optional[datetime] = None


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_SEPARATORS = re.compile(r"[-_]{2,}")


def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """Reduce a user-supplied filename to one safe, flat object-key segment.

    Uploaded filenames are attacker-controlled, so directory components are
    dropped before the name is ever joined into a key. Without this, a name
    like ``../../other-user/secret.pdf`` would escape the caller's prefix.
    """
    candidate: str = (filename or "").strip().replace("\\", "/")
    candidate = candidate.rsplit("/", 1)[-1]
    candidate = unicodedata.normalize("NFKD", candidate)
    candidate = candidate.encode("ascii", "ignore").decode("ascii")
    candidate = _UNSAFE_FILENAME_CHARS.sub("-", candidate)
    candidate = _REPEATED_SEPARATORS.sub("-", candidate).strip("-.")
    if not candidate:
        return "file"

    stem, dot, suffix = candidate.rpartition(".")
    if not dot:
        return candidate[:max_length]

    suffix = suffix[:16]
    stem = (stem or "file")[: max(1, max_length - len(suffix) - 1)]
    return f"{stem}.{suffix}"


def guess_content_type(filename: str, default: str = S3_DEFAULT_CONTENT_TYPE) -> str:
    """Best-effort MIME type from a filename extension."""
    guessed: Optional[str]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or default


def normalize_key(key: str) -> str:
    """Validate and normalize an object key, rejecting traversal segments."""
    normalized: str = (key or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        raise ObjectStorageError("Object key must not be empty")

    parts: list[str] = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ObjectStorageError(f"Object key contains an invalid segment: {key!r}")
    return normalized


def normalize_prefix(prefix: str) -> str:
    """Normalize a listing/deletion prefix. An empty prefix means whole bucket."""
    return (prefix or "").strip().replace("\\", "/").lstrip("/")


def folder_prefix(path: str) -> str:
    """Normalize a folder path to a validated prefix with a trailing slash."""
    normalized: str = normalize_prefix(path).strip("/")
    if not normalized:
        raise ObjectStorageError("Folder path must not be empty")

    parts: list[str] = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ObjectStorageError(f"Folder path contains an invalid segment: {path!r}")
    return "/".join(parts) + "/"


def folder_placeholder_key(path: str) -> str:
    """Key of the 0-byte marker that makes an empty folder visible."""
    return folder_prefix(path) + S3_FOLDER_PLACEHOLDER


def is_placeholder_key(key: str) -> bool:
    """True for the empty-folder marker, which is not a real file."""
    return key.rsplit("/", 1)[-1] == S3_FOLDER_PLACEHOLDER


def folder_name(prefix: str) -> str:
    """Leaf name of a folder prefix: 'a/b/c/' -> 'c'."""
    return prefix.rstrip("/").rsplit("/", 1)[-1]


def to_stored_object(
    key: str,
    payload: dict[str, Any],
) -> StoredObject:
    """Build a StoredObject from a head_object or list_objects_v2 entry."""
    return StoredObject(
        key=key,
        size=payload.get("ContentLength", payload.get("Size")),
        etag=(payload.get("ETag") or "").strip('"') or None,
        content_type=payload.get("ContentType"),
        last_modified=payload.get("LastModified"),
    )
