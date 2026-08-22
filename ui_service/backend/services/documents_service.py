import logging
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status

from doc_agent_client import doc_agent_client as doc_agent
from models.auth import MessageResponse
from models.documents import DocumentTree, DownloadUrlResponse, TreeNode
from object_storage_client import (
    ObjectStorageClient,
    ObjectStorageError,
    StoredObject,
    folder_placeholder_key,
    is_placeholder_key,
    sanitize_filename,
)

load_dotenv()

BUCKET: str = os.getenv("S3_BUCKET_USER_DOCUMENTS", "users_personal_documents")
MAX_FILES_PER_USER: int = int(os.getenv("MAX_FILES_PER_USER", "10"))
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
DOWNLOAD_URL_EXPIRE_SECONDS: int = 300

# Every PDF starts with this signature. Extension and content-type are both
# client-controlled, so the bytes are what actually decide.
_PDF_MAGIC = b"%PDF-"
_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}

logger = logging.getLogger(__name__)

# One path segment: no slashes, no leading/trailing dot, nothing exotic.
# Leading underscore is allowed so names like _3.pdf round-trip after upload.
_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9 ._-]{0,63}$")

storage = ObjectStorageClient(bucket=BUCKET)


# ---------------------------------------------------------------------------
# Path handling
#
# Clients only ever send paths relative to their own folder. Every path is
# validated segment by segment and then prefixed with the user id taken from
# the JWT, so a caller cannot reach another user's folder.
# ---------------------------------------------------------------------------
def _normalize_relative(path: Optional[str]) -> str:
    candidate: str = (path or "").strip().replace("\\", "/")
    if candidate.startswith("/"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Path must be relative to your own folder",
        )

    candidate = candidate.rstrip("/")
    if not candidate:
        return ""

    segments: list[str] = candidate.split("/")
    for segment in segments:
        if not _SEGMENT.fullmatch(segment):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid path segment: {segment!r}",
            )
    return "/".join(segments)


def _user_root(user_id: str) -> str:
    return f"{user_id}/"


def _absolute(user_id: str, relative: str) -> str:
    normalized: str = _normalize_relative(relative)
    if not normalized:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Path is required")
    return f"{user_id}/{normalized}"


def _relative(user_id: str, key: str) -> str:
    root: str = _user_root(user_id)
    return key[len(root):] if key.startswith(root) else key


# ---------------------------------------------------------------------------
# Folder bootstrap
# ---------------------------------------------------------------------------
async def ensure_user_folder(user_id: str) -> None:
    """Create the user's personal folder on first use."""
    if not await storage.folder_exists(user_id):
        await storage.create_folder(user_id)


async def _count_files(user_id: str) -> int:
    """Number of real files the user has, ignoring folder placeholders."""
    objects: list[StoredObject] = await storage.list_objects(_user_root(user_id))
    return len(objects)


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------
def _sort_nodes(nodes: list[TreeNode]) -> None:
    """Folders before files, alphabetical within each group, all the way down."""
    nodes.sort(key=lambda node: (node.type != "folder", node.name.lower()))
    for node in nodes:
        if node.children:
            _sort_nodes(node.children)


def _build_tree(user_id: str, objects: list[StoredObject]) -> tuple[list[TreeNode], int]:
    roots: list[TreeNode] = []
    folders: dict[str, TreeNode] = {}

    def ensure_folder(relative: str) -> TreeNode:
        existing: Optional[TreeNode] = folders.get(relative)
        if existing is not None:
            return existing

        node = TreeNode(
            name=relative.rsplit("/", 1)[-1],
            path=relative,
            type="folder",
            children=[],
        )
        folders[relative] = node

        parent: str = relative.rsplit("/", 1)[0] if "/" in relative else ""
        if parent:
            ensure_folder(parent).children.append(node)
        else:
            roots.append(node)
        return node

    file_count: int = 0
    for obj in objects:
        relative: str = _relative(user_id, obj.key)
        if not relative:
            continue

        segments: list[str] = relative.split("/")
        parent: str = "/".join(segments[:-1])

        # A placeholder is not a file; it only proves its folder exists.
        if is_placeholder_key(obj.key):
            if parent:
                ensure_folder(parent)
            continue

        file_count += 1
        node = TreeNode(
            name=segments[-1],
            path=relative,
            type="file",
            size=obj.size,
            last_modified=obj.last_modified,
            children=[],
        )
        if parent:
            ensure_folder(parent).children.append(node)
        else:
            roots.append(node)

    _sort_nodes(roots)
    return roots, file_count


async def get_tree(user: dict[str, Any]) -> DocumentTree:
    user_id: str = user["id"]
    await ensure_user_folder(user_id)

    objects: list[StoredObject] = await storage.list_objects(
        _user_root(user_id),
        include_placeholders=True,
    )
    nodes, file_count = _build_tree(user_id, objects)
    return DocumentTree(
        nodes=nodes,
        file_count=file_count,
        max_files=MAX_FILES_PER_USER,
    )


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def _validate_pdf(upload: UploadFile) -> tuple[str, int]:
    """Check the upload really is a PDF and return its safe name and size."""
    filename: str = sanitize_filename(upload.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only PDF files are allowed",
        )

    content_type: str = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only PDF files are allowed",
        )

    header: bytes = upload.file.read(len(_PDF_MAGIC))
    upload.file.seek(0, os.SEEK_END)
    size: int = upload.file.tell()
    upload.file.seek(0)

    if header != _PDF_MAGIC:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "File is not a valid PDF",
        )
    if size <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    if size > MAX_UPLOAD_BYTES:
        limit_mb: int = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File is too large (limit {limit_mb} MB)",
        )
    return filename, size


async def upload_document(
    user: dict[str, Any],
    folder: Optional[str],
    upload: UploadFile,
) -> TreeNode:
    user_id: str = user["id"]
    filename, _ = _validate_pdf(upload)

    await ensure_user_folder(user_id)

    folder_relative: str = _normalize_relative(folder)
    if folder_relative and not await storage.folder_exists(f"{user_id}/{folder_relative}"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")

    if await _count_files(user_id) >= MAX_FILES_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"File limit reached. You can store up to {MAX_FILES_PER_USER} files.",
        )

    relative: str = f"{folder_relative}/{filename}" if folder_relative else filename
    key: str = f"{user_id}/{relative}"
    if await storage.exists(key):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A file with this name already exists in that folder",
        )

    stored: StoredObject = await storage.upload_fileobj(
        key,
        upload.file,
        content_type="application/pdf",
    )
    try:
        await doc_agent.ingest_document(user_id, relative)
    except Exception:
        try:
            await storage.delete(key)
        except ObjectStorageError:
            logger.exception("Failed to roll back S3 upload after ingest error: %s", key)
        raise
    return TreeNode(
        name=filename,
        path=relative,
        type="file",
        size=stored.size,
        last_modified=stored.last_modified,
        children=[],
    )


async def delete_file(user: dict[str, Any], path: str) -> MessageResponse:
    user_id: str = user["id"]
    relative: str = _normalize_relative(path)
    key: str = _absolute(user_id, relative)
    if is_placeholder_key(key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file")
    if not await storage.exists(key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    await _delete_document_vectors(user_id, relative)
    await storage.delete(key)
    return MessageResponse(message="File deleted")


async def _delete_document_vectors(user_id: str, relative_path: str) -> None:
    await doc_agent.delete_document_vectors(user_id, relative_path)


async def delete_all_user_files(user_id: str) -> int:
    """Delete every object under the user's S3 prefix, including folder markers."""
    uid: str = user_id.strip()
    if not uid or "/" in uid or "\\" in uid or uid in {".", ".."}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user_id")
    try:
        return await storage.delete_prefix(_user_root(uid))
    except ObjectStorageError as exc:
        logger.exception("Failed to delete S3 documents for %s", uid)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to delete user documents from storage",
        ) from exc


async def move_file(user: dict[str, Any], path: str, folder: Optional[str]) -> TreeNode:
    """Copy a file into another folder, then delete the original."""
    user_id: str = user["id"]
    source_key: str = _absolute(user_id, path)
    if is_placeholder_key(source_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file")
    if not await storage.exists(source_key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    filename: str = source_key.rsplit("/", 1)[-1]
    dest_folder: str = _normalize_relative(folder)
    current_folder: str = path.rsplit("/", 1)[0] if "/" in path else ""
    if dest_folder == current_folder:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "File is already in that folder",
        )

    if dest_folder and not await storage.folder_exists(f"{user_id}/{dest_folder}"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")

    dest_relative: str = f"{dest_folder}/{filename}" if dest_folder else filename
    dest_key: str = f"{user_id}/{dest_relative}"
    if await storage.exists(dest_key):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A file with this name already exists in that folder",
        )

    stored: StoredObject = await storage.copy(source_key, dest_key)
    await _delete_document_vectors(user_id, _normalize_relative(path))
    await storage.delete(source_key)
    return TreeNode(
        name=filename,
        path=dest_relative,
        type="file",
        size=stored.size,
        last_modified=stored.last_modified,
        children=[],
    )


async def get_download_url(user: dict[str, Any], path: str) -> DownloadUrlResponse:
    key: str = _absolute(user["id"], path)
    if not await storage.exists(key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    url: str = await storage.presigned_get_url(
        key,
        expires_in=DOWNLOAD_URL_EXPIRE_SECONDS,
        download_as=key.rsplit("/", 1)[-1],
    )
    return DownloadUrlResponse(url=url, expires_in=DOWNLOAD_URL_EXPIRE_SECONDS)


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
async def create_folder(user: dict[str, Any], path: str) -> TreeNode:
    user_id: str = user["id"]
    relative: str = _normalize_relative(path)
    if not relative:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Folder name is required")

    await ensure_user_folder(user_id)

    parent: str = relative.rsplit("/", 1)[0] if "/" in relative else ""
    if parent and not await storage.folder_exists(f"{user_id}/{parent}"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parent folder not found")

    full: str = f"{user_id}/{relative}"
    if await storage.folder_exists(full):
        raise HTTPException(status.HTTP_409_CONFLICT, "Folder already exists")

    await storage.create_folder(full)
    return TreeNode(
        name=relative.rsplit("/", 1)[-1],
        path=relative,
        type="folder",
        children=[],
    )


async def delete_folder(user: dict[str, Any], path: str) -> MessageResponse:
    """Delete a folder, but only once it holds nothing.

    Refusing to delete a non-empty folder is a product rule, not a storage one:
    S3 would happily drop every key under the prefix in one call.
    """
    user_id: str = user["id"]
    relative: str = _normalize_relative(path)
    if not relative:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your personal folder cannot be deleted",
        )

    full: str = f"{user_id}/{relative}"
    contents: list[StoredObject] = await storage.list_objects(
        f"{full}/",
        include_placeholders=True,
    )
    if not contents:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Folder not found")

    placeholder: str = folder_placeholder_key(full)
    remaining: list[StoredObject] = [
        item for item in contents if item.key != placeholder
    ]
    if remaining:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Folder is not empty. Delete everything inside it first.",
        )

    await storage.delete_folder(full)
    return MessageResponse(message="Folder deleted")
