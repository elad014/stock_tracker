from io import BytesIO
from types import SimpleNamespace
import unittest

from test_support import import_project_module

documents_service = import_project_module("services.documents_service", "common", "ui_service/backend", model_stubs=True)
HTTPException = documents_service.HTTPException
StoredObject = documents_service.StoredObject


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.folders: set[str] = set()
        self.deleted: list[str] = []
        self.created: list[str] = []
        self.copied: list[tuple[str, str]] = []
        self.presigned: list[tuple[str, str]] = []

    async def folder_exists(self, path: str) -> bool:
        return path in self.folders or any(key.startswith(path.rstrip("/") + "/") for key in self.objects)

    async def create_folder(self, path: str) -> None:
        self.created.append(path)
        self.folders.add(path)

    async def list_objects(self, prefix: str, include_placeholders: bool = False, **_kwargs):
        return [obj for key, obj in self.objects.items() if key.startswith(prefix) and (include_placeholders or not documents_service.is_placeholder_key(key))]

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def upload_fileobj(self, key: str, fileobj, content_type: str):
        data = fileobj.read()
        fileobj.seek(0)
        obj = StoredObject(key=key, size=len(data))
        self.objects[key] = obj
        return obj

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)

    async def copy(self, source: str, dest: str):
        self.copied.append((source, dest))
        obj = StoredObject(key=dest, size=self.objects[source].size)
        self.objects[dest] = obj
        return obj

    async def presigned_get_url(self, key: str, expires_in: int, download_as: str) -> str:
        self.presigned.append((key, download_as))
        return f"https://download/{download_as}"

    async def delete_prefix(self, prefix: str) -> int:
        keys = [key for key in self.objects if key.startswith(prefix)]
        for key in keys:
            self.objects.pop(key)
        return len(keys)

    async def delete_folder(self, path: str) -> None:
        self.deleted.append(path)
        self.folders.discard(path)


class FakeDocAgent:
    def __init__(self) -> None:
        self.ingested: list[tuple[str, str]] = []
        self.deleted_vectors: list[tuple[str, str]] = []
        self.fail_ingest = False

    async def ingest_document(self, user_id: str, relative: str):
        self.ingested.append((user_id, relative))
        if self.fail_ingest:
            raise RuntimeError("ingest failed")
        return {}

    async def delete_document_vectors(self, user_id: str, relative: str):
        self.deleted_vectors.append((user_id, relative))
        return {}


class DocumentsServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.storage = FakeStorage()
        self.doc_agent = FakeDocAgent()
        documents_service.storage = self.storage
        documents_service.doc_agent = self.doc_agent
        documents_service.MAX_FILES_PER_USER = 10
        documents_service.MAX_UPLOAD_BYTES = 1024

    def upload(self, filename="Report.pdf", content_type="application/pdf", data=b"%PDF-hello"):
        return SimpleNamespace(filename=filename, content_type=content_type, file=BytesIO(data))

    def test_normalize_relative_rejects_absolute_or_traversal_paths(self) -> None:
        with self.assertRaises(HTTPException):
            documents_service._normalize_relative("/other/file.pdf")
        with self.assertRaises(HTTPException):
            documents_service._normalize_relative("../file.pdf")
        self.assertEqual(documents_service._normalize_relative("Reports\\2026"), "Reports/2026")

    def test_build_tree_ignores_placeholders_and_sorts_folders_first(self) -> None:
        objects = [
            StoredObject(key="u1/b.pdf", size=2),
            StoredObject(key="u1/Reports/.emptyFolderPlaceholder", size=0),
            StoredObject(key="u1/Reports/a.pdf", size=1),
        ]

        nodes, file_count = documents_service._build_tree("u1", objects)

        self.assertEqual(file_count, 2)
        self.assertEqual([node.name for node in nodes], ["Reports", "b.pdf"])
        self.assertEqual(nodes[0].children[0].name, "a.pdf")

    def test_validate_pdf_rejects_wrong_extension_type_magic_and_size(self) -> None:
        for upload in [
            self.upload(filename="a.txt"),
            self.upload(content_type="text/plain"),
            self.upload(data=b"not pdf"),
            self.upload(data=b"%PDF-" + b"x" * 2048),
        ]:
            with self.subTest(upload=upload):
                with self.assertRaises(HTTPException):
                    documents_service._validate_pdf(upload)

    async def test_upload_document_stores_file_and_triggers_ingest(self) -> None:
        self.storage.folders.update({"u1", "u1/Reports"})

        node = await documents_service.upload_document({"id": "u1"}, "Reports", self.upload("My Report.pdf"))

        self.assertEqual(node.path, "Reports/My-Report.pdf")
        self.assertIn("u1/Reports/My-Report.pdf", self.storage.objects)
        self.assertEqual(self.doc_agent.ingested, [("u1", "Reports/My-Report.pdf")])

    async def test_upload_document_rolls_back_storage_when_ingest_fails(self) -> None:
        self.storage.folders.add("u1")
        self.doc_agent.fail_ingest = True

        with self.assertRaises(RuntimeError):
            await documents_service.upload_document({"id": "u1"}, None, self.upload("a.pdf"))

        self.assertEqual(self.storage.deleted, ["u1/a.pdf"])

    async def test_upload_document_enforces_file_limit(self) -> None:
        self.storage.folders.add("u1")
        documents_service.MAX_FILES_PER_USER = 1
        self.storage.objects["u1/existing.pdf"] = StoredObject(key="u1/existing.pdf")

        with self.assertRaises(HTTPException) as caught:
            await documents_service.upload_document({"id": "u1"}, None, self.upload("new.pdf"))

        self.assertEqual(caught.exception.status_code, 409)

    async def test_delete_file_deletes_vectors_before_object(self) -> None:
        self.storage.objects["u1/a.pdf"] = StoredObject(key="u1/a.pdf")

        response = await documents_service.delete_file({"id": "u1"}, "a.pdf")

        self.assertEqual(response.message, "File deleted")
        self.assertEqual(self.doc_agent.deleted_vectors, [("u1", "a.pdf")])
        self.assertEqual(self.storage.deleted, ["u1/a.pdf"])

    async def test_move_file_checks_destination_and_updates_vectors(self) -> None:
        self.storage.objects["u1/a.pdf"] = StoredObject(key="u1/a.pdf", size=12)
        self.storage.folders.add("u1/Reports")

        node = await documents_service.move_file({"id": "u1"}, "a.pdf", "Reports")

        self.assertEqual(node.path, "Reports/a.pdf")
        self.assertEqual(self.storage.copied, [("u1/a.pdf", "u1/Reports/a.pdf")])
        self.assertEqual(self.doc_agent.deleted_vectors, [("u1", "a.pdf")])

    async def test_delete_folder_rejects_non_empty_folder(self) -> None:
        self.storage.objects["u1/Reports/.emptyFolderPlaceholder"] = StoredObject(key="u1/Reports/.emptyFolderPlaceholder")
        self.storage.objects["u1/Reports/a.pdf"] = StoredObject(key="u1/Reports/a.pdf")

        with self.assertRaises(HTTPException) as caught:
            await documents_service.delete_folder({"id": "u1"}, "Reports")

        self.assertEqual(caught.exception.status_code, 409)

    async def test_get_download_url_presigns_existing_user_file(self) -> None:
        self.storage.objects["u1/a.pdf"] = StoredObject(key="u1/a.pdf")

        response = await documents_service.get_download_url({"id": "u1"}, "a.pdf")

        self.assertEqual(response.url, "https://download/a.pdf")
        self.assertEqual(response.expires_in, documents_service.DOWNLOAD_URL_EXPIRE_SECONDS)


if __name__ == "__main__":
    unittest.main()


class DocumentIsolationAndFailureRegressionTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "DOCUMENTS"

    def setUp(self) -> None:
        self.storage = FakeStorage()
        self.doc_agent = FakeDocAgent()
        documents_service.storage = self.storage
        documents_service.doc_agent = self.doc_agent
        documents_service.MAX_FILES_PER_USER = 10
        documents_service.MAX_UPLOAD_BYTES = 1024

    def upload(self, filename="Report.pdf", content_type="application/pdf", data=b"%PDF-hello"):
        return SimpleNamespace(filename=filename, content_type=content_type, file=BytesIO(data))

    async def test_user_cannot_download_another_users_document_by_changing_path(self) -> None:
        """Keep document download scoped to the authenticated user's folder."""
        self.storage.objects["u2/secret.pdf"] = StoredObject(key="u2/secret.pdf")

        with self.assertRaises(HTTPException) as caught:
            await documents_service.get_download_url({"id": "u1"}, "u2/secret.pdf")

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.storage.presigned, [])

    async def test_user_cannot_delete_another_users_document_by_changing_path(self) -> None:
        """Keep document deletion scoped to the authenticated user's folder."""
        self.storage.objects["u2/secret.pdf"] = StoredObject(key="u2/secret.pdf")

        with self.assertRaises(HTTPException) as caught:
            await documents_service.delete_file({"id": "u1"}, "u2/secret.pdf")

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.storage.deleted, [])
        self.assertEqual(self.doc_agent.deleted_vectors, [])

    async def test_duplicate_filename_is_rejected_before_storage_write_or_ingest(self) -> None:
        """Reject duplicate document filenames before upload or vector processing."""
        self.storage.folders.add("u1")
        self.storage.objects["u1/a.pdf"] = StoredObject(key="u1/a.pdf")

        with self.assertRaises(HTTPException) as caught:
            await documents_service.upload_document({"id": "u1"}, None, self.upload("a.pdf"))

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.doc_agent.ingested, [])
        self.assertEqual(len(self.storage.objects), 1)

    async def test_storage_upload_failure_does_not_trigger_document_ingest(self) -> None:
        """Do not call doc-agent when storage upload fails."""
        self.storage.folders.add("u1")

        async def fail_upload(*_args, **_kwargs):
            raise documents_service.ObjectStorageError("storage unavailable")

        self.storage.upload_fileobj = fail_upload

        with self.assertRaises(documents_service.ObjectStorageError):
            await documents_service.upload_document({"id": "u1"}, None, self.upload("a.pdf"))

        self.assertEqual(self.doc_agent.ingested, [])

    async def test_vector_cleanup_failure_prevents_physical_file_delete(self) -> None:
        """Do not delete a PDF when vector cleanup fails first."""
        self.storage.objects["u1/a.pdf"] = StoredObject(key="u1/a.pdf")

        async def fail_vector_delete(*_args, **_kwargs):
            raise RuntimeError("vector cleanup failed")

        self.doc_agent.delete_document_vectors = fail_vector_delete

        with self.assertRaisesRegex(RuntimeError, "vector cleanup failed"):
            await documents_service.delete_file({"id": "u1"}, "a.pdf")

        self.assertIn("u1/a.pdf", self.storage.objects)
        self.assertEqual(self.storage.deleted, [])

