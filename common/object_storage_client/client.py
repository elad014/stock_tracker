"""Object storage client for Supabase Storage over the S3 protocol.

Supabase exposes an S3-compatible endpoint, so the same boto3 client works
against Supabase now and against real AWS S3 later by clearing
``S3_ENDPOINT_URL``.

Environment variables:
- ``S3_ENDPOINT_URL`` — e.g.
  ``https://<project-ref>.storage.supabase.co/storage/v1/s3``
  (leave unset for AWS S3, which resolves its endpoint from the region)
- ``S3_REGION`` — project region shown on the Supabase storage settings page
- ``S3_ACCESS_KEY_ID`` / ``S3_SECRET_ACCESS_KEY`` — S3 access keys generated on
  that same page. They grant full access to every bucket and bypass RLS, so
  they must stay server-side.
- ``S3_BUCKET`` — default bucket name

Supabase does not implement ACLs, object tagging, server-side encryption
headers, or bucket versioning, so none of those are used here. Deletes are
permanent and cannot be undone.
"""

import asyncio
import json
import logging
import os
import threading
from typing import Any, BinaryIO, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from boto3.s3.transfer import TransferConfig
from dotenv import load_dotenv

from constant import (
    S3_ADDRESSING_STYLE,
    S3_CONNECT_TIMEOUT_SECONDS,
    S3_DEFAULT_REGION,
    S3_MAX_ATTEMPTS,
    S3_MULTIPART_CHUNK_BYTES,
    S3_MULTIPART_THRESHOLD_BYTES,
    S3_PRESIGNED_EXPIRE_SECONDS,
    S3_READ_TIMEOUT_SECONDS,
    S3_REQUEST_CHECKSUM,
    S3_RESPONSE_CHECKSUM,
    S3_SIGNATURE_VERSION,
)
from object_storage_client.util import (
    ObjectStorageError,
    StoredObject,
    folder_name,
    folder_placeholder_key,
    folder_prefix,
    guess_content_type,
    is_placeholder_key,
    normalize_key,
    normalize_prefix,
    to_stored_object,
)

logger = logging.getLogger(__name__)

load_dotenv()

_MISSING_OBJECT_CODES = {"404", "NoSuchKey", "NotFound"}

# boto3 clients are thread-safe and hold a connection pool, so instances that
# share credentials reuse one client instead of each opening its own pool.
_shared_clients: dict[tuple[str, str, str], Any] = {}
_shared_clients_lock = threading.Lock()


class ObjectStorageClient:
    """S3-protocol object storage client with an async-friendly surface.

    boto3 is synchronous, so every public method runs the blocking call in a
    worker thread to keep the FastAPI event loop free.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ) -> None:
        self._bucket: str = bucket or os.getenv("S3_BUCKET", "")
        self._endpoint_url: Optional[str] = (
            endpoint_url or os.getenv("S3_ENDPOINT_URL", "") or None
        )
        self._region: str = region or os.getenv("S3_REGION", "") or S3_DEFAULT_REGION
        self._access_key_id: str = access_key_id or os.getenv("S3_ACCESS_KEY_ID", "")
        self._secret_access_key: str = secret_access_key or os.getenv(
            "S3_SECRET_ACCESS_KEY", ""
        )
    # ------------------------------------------------------------------
    # Configuration / connection
    # ------------------------------------------------------------------
    @property
    def bucket(self) -> str:
        if not self._bucket:
            raise ObjectStorageError(
                "No bucket configured. Construct the client with "
                "ObjectStorageClient(bucket=...), set S3_BUCKET in .env, or pass "
                "bucket=... per call."
            )
        return self._bucket

    def has_credentials(self) -> bool:
        """True when credentials are present, regardless of bucket."""
        return bool(self._access_key_id and self._secret_access_key)

    def is_configured(self) -> bool:
        """True when enough config is present to attempt a call."""
        return bool(self._bucket) and self.has_credentials()

    def _build_client(self) -> Any:
        if not self._access_key_id or not self._secret_access_key:
            raise ObjectStorageError(
                "S3 credentials missing. Set S3_ACCESS_KEY_ID and "
                "S3_SECRET_ACCESS_KEY in .env"
            )

        config = Config(
            signature_version=S3_SIGNATURE_VERSION,
            s3={"addressing_style": S3_ADDRESSING_STYLE},
            connect_timeout=S3_CONNECT_TIMEOUT_SECONDS,
            read_timeout=S3_READ_TIMEOUT_SECONDS,
            retries={"max_attempts": S3_MAX_ATTEMPTS, "mode": "standard"},
            request_checksum_calculation=S3_REQUEST_CHECKSUM,
            response_checksum_validation=S3_RESPONSE_CHECKSUM,
        )
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            config=config,
        )

    def _s3(self) -> Any:
        """Build the boto3 client on first use, shared across same-credential instances.

        Construction is deferred so importing this module never fails on a
        service that has no storage credentials configured.
        """
        cache_key = (self._endpoint_url or "", self._region, self._access_key_id)
        client = _shared_clients.get(cache_key)
        if client is None:
            with _shared_clients_lock:
                client = _shared_clients.get(cache_key)
                if client is None:
                    client = self._build_client()
                    _shared_clients[cache_key] = client
        return client

    def _resolve_bucket(self, bucket: Optional[str]) -> str:
        return bucket or self.bucket

    @staticmethod
    def _error_code(exc: ClientError) -> str:
        return str(exc.response.get("Error", {}).get("Code", ""))

    @staticmethod
    def _fail(operation: str, key: str, exc: Exception) -> ObjectStorageError:
        logger.error("Object storage %s failed for %s: %s", operation, key, exc)
        return ObjectStorageError(f"Object storage {operation} failed for {key}: {exc}")

    # ------------------------------------------------------------------
    # Blocking implementations (run in a worker thread)
    # ------------------------------------------------------------------
    def _put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[dict[str, str]],
        bucket: str,
    ) -> StoredObject:
        params: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if metadata:
            params["Metadata"] = metadata

        response = self._s3().put_object(**params)
        return StoredObject(
            key=key,
            size=len(data),
            etag=(response.get("ETag") or "").strip('"') or None,
            content_type=content_type,
        )

    def _put_fileobj(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str,
        metadata: Optional[dict[str, str]],
        bucket: str,
    ) -> StoredObject:
        extra_args: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata

        transfer = TransferConfig(
            multipart_threshold=S3_MULTIPART_THRESHOLD_BYTES,
            multipart_chunksize=S3_MULTIPART_CHUNK_BYTES,
        )
        client = self._s3()
        client.upload_fileobj(
            fileobj,
            bucket,
            key,
            ExtraArgs=extra_args,
            Config=transfer,
        )
        # upload_fileobj returns nothing, so read back the stored size/etag.
        head = client.head_object(Bucket=bucket, Key=key)
        return to_stored_object(key, head)

    def _get_bytes(self, key: str, bucket: str) -> bytes:
        response = self._s3().get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            return bytes(body.read())
        finally:
            body.close()

    def _head(self, key: str, bucket: str) -> Optional[dict[str, Any]]:
        try:
            return dict(self._s3().head_object(Bucket=bucket, Key=key))
        except ClientError as exc:
            if self._error_code(exc) in _MISSING_OBJECT_CODES:
                return None
            raise

    def _paginate(
        self,
        prefix: str,
        bucket: str,
        delimiter: Optional[str],
    ) -> Any:
        paginator = self._s3().get_paginator("list_objects_v2")
        page_args: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if delimiter:
            page_args["Delimiter"] = delimiter
        return paginator.paginate(**page_args)

    def _list(
        self,
        prefix: str,
        bucket: str,
        max_keys: Optional[int],
        delimiter: Optional[str] = None,
        include_placeholders: bool = False,
    ) -> list[StoredObject]:
        results: list[StoredObject] = []
        for page in self._paginate(prefix, bucket, delimiter):
            for entry in page.get("Contents", []):
                key = str(entry["Key"])
                if not include_placeholders and is_placeholder_key(key):
                    continue
                results.append(to_stored_object(key, entry))
                if max_keys is not None and len(results) >= max_keys:
                    return results
        return results

    def _list_folders(self, prefix: str, bucket: str) -> list[str]:
        folders: list[str] = []
        for page in self._paginate(prefix, bucket, "/"):
            for entry in page.get("CommonPrefixes", []):
                folders.append(str(entry["Prefix"]))
        return sorted(folders)

    def _delete_keys(self, keys: list[str], bucket: str) -> int:
        # DeleteObject, not DeleteObjects. boto3 marks the batch API as
        # checksum-required, and Supabase Storage rejects those headers with
        # an empty error: "An error occurred () when calling the DeleteObjects
        # operation". Single-key delete has no checksum requirement.
        client = self._s3()
        deleted = 0
        for key in keys:
            try:
                client.delete_object(Bucket=bucket, Key=key)
                deleted += 1
            except ClientError as exc:
                logger.error("Failed to delete %s: %s", key, exc)
        return deleted

    def _delete_prefix(self, prefix: str, bucket: str) -> int:
        # Placeholders must be included or the emptied folder would linger.
        keys = [
            obj.key
            for obj in self._list(prefix, bucket, None, include_placeholders=True)
        ]
        if not keys:
            return 0
        return self._delete_keys(keys, bucket)

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------
    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
        bucket: Optional[str] = None,
    ) -> StoredObject:
        """Upload an in-memory payload. Use for small files and JSON blobs."""
        normalized = normalize_key(key)
        resolved_type = content_type or guess_content_type(normalized)
        try:
            return await asyncio.to_thread(
                self._put_bytes,
                normalized,
                data,
                resolved_type,
                metadata,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("upload", normalized, exc) from exc

    async def upload_fileobj(
        self,
        key: str,
        fileobj: BinaryIO,
        *,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
        bucket: Optional[str] = None,
    ) -> StoredObject:
        """Stream a file-like object, switching to multipart for large files.

        Preferred for user uploads so the whole file never sits in memory.
        """
        normalized = normalize_key(key)
        resolved_type = content_type or guess_content_type(normalized)
        try:
            return await asyncio.to_thread(
                self._put_fileobj,
                normalized,
                fileobj,
                resolved_type,
                metadata,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("upload", normalized, exc) from exc

    async def upload_text(
        self,
        key: str,
        text: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
        metadata: Optional[dict[str, str]] = None,
        bucket: Optional[str] = None,
    ) -> StoredObject:
        return await self.upload_bytes(
            key,
            text.encode("utf-8"),
            content_type=content_type,
            metadata=metadata,
            bucket=bucket,
        )

    async def upload_json(
        self,
        key: str,
        payload: Any,
        *,
        metadata: Optional[dict[str, str]] = None,
        bucket: Optional[str] = None,
    ) -> StoredObject:
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return await self.upload_bytes(
            key,
            body.encode("utf-8"),
            content_type="application/json; charset=utf-8",
            metadata=metadata,
            bucket=bucket,
        )

    async def download_bytes(
        self,
        key: str,
        *,
        bucket: Optional[str] = None,
    ) -> bytes:
        normalized = normalize_key(key)
        try:
            return await asyncio.to_thread(
                self._get_bytes,
                normalized,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("download", normalized, exc) from exc

    async def download_text(
        self,
        key: str,
        *,
        encoding: str = "utf-8",
        bucket: Optional[str] = None,
    ) -> str:
        raw = await self.download_bytes(key, bucket=bucket)
        return raw.decode(encoding, errors="replace")

    async def stat(
        self,
        key: str,
        *,
        bucket: Optional[str] = None,
    ) -> Optional[StoredObject]:
        """Return object metadata, or None when the key does not exist."""
        normalized = normalize_key(key)
        try:
            head = await asyncio.to_thread(
                self._head,
                normalized,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("stat", normalized, exc) from exc
        if head is None:
            return None
        return to_stored_object(normalized, head)

    async def exists(self, key: str, *, bucket: Optional[str] = None) -> bool:
        return await self.stat(key, bucket=bucket) is not None

    async def list_objects(
        self,
        prefix: str = "",
        *,
        max_keys: Optional[int] = None,
        recursive: bool = True,
        include_placeholders: bool = False,
        bucket: Optional[str] = None,
    ) -> list[StoredObject]:
        """List files under a prefix.

        With ``recursive=False`` only direct children are returned, so nested
        folders collapse instead of being walked. Empty-folder placeholders are
        hidden unless explicitly requested.
        """
        normalized = normalize_prefix(prefix)
        try:
            return await asyncio.to_thread(
                self._list,
                normalized,
                self._resolve_bucket(bucket),
                max_keys,
                None if recursive else "/",
                include_placeholders,
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("list", normalized or "<bucket root>", exc) from exc

    # ------------------------------------------------------------------
    # Folders
    #
    # S3 has no folders. A folder is just a shared key prefix, so creating one
    # means writing the 0-byte marker the Supabase dashboard looks for, and
    # deleting one means deleting every key beneath it.
    # ------------------------------------------------------------------
    async def create_folder(self, path: str, *, bucket: Optional[str] = None) -> str:
        """Create an empty folder and return its prefix.

        Only needed to make an *empty* folder visible. Uploading to a nested key
        makes the intermediate folders appear on their own.
        """
        prefix = folder_prefix(path)
        await self.upload_bytes(folder_placeholder_key(path), b"", bucket=bucket)
        return prefix

    async def delete_folder(self, path: str, *, bucket: Optional[str] = None) -> int:
        """Recursively delete a folder, returning how many objects were removed."""
        return await self.delete_prefix(folder_prefix(path), bucket=bucket)

    async def list_folders(
        self,
        prefix: str = "",
        *,
        bucket: Optional[str] = None,
    ) -> list[str]:
        """List direct sub-folder prefixes, each ending with a slash."""
        normalized = normalize_prefix(prefix)
        if normalized and not normalized.endswith("/"):
            normalized = f"{normalized}/"
        try:
            return await asyncio.to_thread(
                self._list_folders,
                normalized,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("list_folders", normalized or "<bucket root>", exc) from exc

    async def list_folder_names(
        self,
        prefix: str = "",
        *,
        bucket: Optional[str] = None,
    ) -> list[str]:
        """Same as list_folders but returns leaf names instead of full prefixes."""
        prefixes = await self.list_folders(prefix, bucket=bucket)
        return [folder_name(item) for item in prefixes]

    async def folder_exists(self, path: str, *, bucket: Optional[str] = None) -> bool:
        """True when at least one object exists under the folder prefix."""
        found = await self.list_objects(
            folder_prefix(path),
            max_keys=1,
            include_placeholders=True,
            bucket=bucket,
        )
        return bool(found)

    async def list_buckets(self) -> list[str]:
        """Names of every bucket the credentials can see. Useful for diagnostics."""
        try:
            response = await asyncio.to_thread(lambda: self._s3().list_buckets())
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("list_buckets", "<account>", exc) from exc
        return [str(entry["Name"]) for entry in response.get("Buckets", [])]

    async def copy(
        self,
        source_key: str,
        dest_key: str,
        *,
        bucket: Optional[str] = None,
    ) -> StoredObject:
        """Copy one object inside the same bucket."""
        source = normalize_key(source_key)
        dest = normalize_key(dest_key)
        resolved = self._resolve_bucket(bucket)
        try:
            await asyncio.to_thread(
                lambda: self._s3().copy_object(
                    Bucket=resolved,
                    CopySource={"Bucket": resolved, "Key": source},
                    Key=dest,
                )
            )
            head = await asyncio.to_thread(self._head, dest, resolved)
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("copy", f"{source} -> {dest}", exc) from exc
        if head is None:
            raise ObjectStorageError(f"Copied object is missing: {dest}")
        return to_stored_object(dest, head)

    async def delete(self, key: str, *, bucket: Optional[str] = None) -> None:
        """Delete one object. Supabase has no versioning, so this is permanent."""
        normalized = normalize_key(key)
        resolved = self._resolve_bucket(bucket)
        try:
            await asyncio.to_thread(
                lambda: self._s3().delete_object(Bucket=resolved, Key=normalized)
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("delete", normalized, exc) from exc

    async def delete_prefix(
        self,
        prefix: str,
        *,
        bucket: Optional[str] = None,
    ) -> int:
        """Delete every object under a prefix and return how many were removed."""
        normalized = normalize_prefix(prefix)
        if not normalized:
            raise ObjectStorageError(
                "Refusing to delete with an empty prefix (would empty the bucket)"
            )
        try:
            return await asyncio.to_thread(
                self._delete_prefix,
                normalized,
                self._resolve_bucket(bucket),
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("delete_prefix", normalized, exc) from exc

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int = S3_PRESIGNED_EXPIRE_SECONDS,
        download_as: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> str:
        """Time-limited download URL, so private objects never need a proxy."""
        normalized = normalize_key(key)
        params: dict[str, Any] = {
            "Bucket": self._resolve_bucket(bucket),
            "Key": normalized,
        }
        if download_as:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{download_as}"'
            )
        try:
            return await asyncio.to_thread(
                lambda: str(
                    self._s3().generate_presigned_url(
                        "get_object",
                        Params=params,
                        ExpiresIn=expires_in,
                    )
                )
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("presign_get", normalized, exc) from exc

    async def presigned_put_url(
        self,
        key: str,
        *,
        expires_in: int = S3_PRESIGNED_EXPIRE_SECONDS,
        content_type: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> str:
        """Time-limited upload URL for browser-direct uploads."""
        normalized = normalize_key(key)
        params: dict[str, Any] = {
            "Bucket": self._resolve_bucket(bucket),
            "Key": normalized,
            "ContentType": content_type or guess_content_type(normalized),
        }
        try:
            return await asyncio.to_thread(
                lambda: str(
                    self._s3().generate_presigned_url(
                        "put_object",
                        Params=params,
                        ExpiresIn=expires_in,
                    )
                )
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._fail("presign_put", normalized, exc) from exc

    async def health_check(self, *, bucket: Optional[str] = None) -> bool:
        """Verify credentials and bucket reachability with a HeadBucket call."""
        try:
            resolved = self._resolve_bucket(bucket)
            await asyncio.to_thread(lambda: self._s3().head_bucket(Bucket=resolved))
            return True
        except (ClientError, BotoCoreError, ObjectStorageError) as exc:
            logger.error("Object storage health check failed: %s", exc)
            return False


# Default instance bound to S3_BUCKET. Services that own a specific bucket
# should build their own: ObjectStorageClient(bucket="their_bucket").
object_storage = ObjectStorageClient()
