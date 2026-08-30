import unittest
from types import SimpleNamespace

from test_support import import_project_module

client_module = import_project_module("object_storage_client.client", "common")


class ObjectStorageClientCacheTests(unittest.TestCase):
    COMPONENT = "CACHE / STORAGE"

    def setUp(self) -> None:
        client_module._shared_clients.clear()
        self.original_boto3_client = client_module.boto3.client

    def tearDown(self) -> None:
        client_module.boto3.client = self.original_boto3_client
        client_module._shared_clients.clear()

    def test_s3_clients_are_reused_for_same_cache_key(self) -> None:
        created_clients = []

        def fake_boto3_client(service_name, **kwargs):
            fake_client = SimpleNamespace(service_name=service_name, kwargs=kwargs)
            created_clients.append(fake_client)
            return fake_client

        client_module.boto3.client = fake_boto3_client

        first = client_module.ObjectStorageClient(
            bucket="documents",
            endpoint_url="https://storage.example.test",
            region="eu-test-1",
            access_key_id="access-key-1",
            secret_access_key="secret-1",
        )
        second = client_module.ObjectStorageClient(
            bucket="documents",
            endpoint_url="https://storage.example.test",
            region="eu-test-1",
            access_key_id="access-key-1",
            secret_access_key="secret-1",
        )
        different_access_key = client_module.ObjectStorageClient(
            bucket="documents",
            endpoint_url="https://storage.example.test",
            region="eu-test-1",
            access_key_id="access-key-2",
            secret_access_key="secret-2",
        )

        self.assertIs(first._s3(), second._s3())
        self.assertIsNot(first._s3(), different_access_key._s3())
        self.assertEqual(len(created_clients), 2)
        self.assertEqual(created_clients[0].service_name, "s3")
        self.assertEqual(created_clients[0].kwargs["endpoint_url"], "https://storage.example.test")
        self.assertEqual(created_clients[0].kwargs["region_name"], "eu-test-1")


if __name__ == "__main__":
    unittest.main()
