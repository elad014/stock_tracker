import unittest

from test_support import import_project_module

util = import_project_module("object_storage_client.util", "common")


class ObjectStorageUtilTests(unittest.TestCase):
    def test_sanitize_filename_drops_directories_and_unsafe_characters(self) -> None:
        sanitized = util.sanitize_filename("../My Report (final).pdf")
        self.assertFalse("/" in sanitized or "\\" in sanitized)
        self.assertTrue(sanitized.startswith("My-Report-final"))
        self.assertTrue(sanitized.endswith(".pdf"))
        self.assertEqual(util.sanitize_filename("***"), "file")

    def test_sanitize_filename_limits_long_stem_and_suffix(self) -> None:
        result = util.sanitize_filename("a" * 200 + ".verylongsuffix", max_length=20)
        self.assertLessEqual(len(result), 20)
        self.assertTrue(result.endswith(".verylongsuffix"[:17]))

    def test_normalize_key_rejects_empty_and_traversal_segments(self) -> None:
        self.assertEqual(util.normalize_key("/u1\\folder/file.pdf"), "u1/folder/file.pdf")
        for key in ["", "u1//file", "u1/../file", "u1/./file"]:
            with self.subTest(key=key):
                with self.assertRaises(util.ObjectStorageError):
                    util.normalize_key(key)

    def test_folder_helpers_create_placeholder_key_and_leaf_name(self) -> None:
        self.assertEqual(util.folder_prefix("u1/Reports"), "u1/Reports/")
        self.assertEqual(util.folder_placeholder_key("u1/Reports"), "u1/Reports/.emptyFolderPlaceholder")
        self.assertTrue(util.is_placeholder_key("u1/Reports/.emptyFolderPlaceholder"))
        self.assertEqual(util.folder_name("u1/Reports/"), "Reports")

    def test_guess_content_type_uses_default_when_unknown(self) -> None:
        self.assertEqual(util.guess_content_type("file.pdf"), "application/pdf")
        self.assertEqual(util.guess_content_type("file.unknownext"), util.S3_DEFAULT_CONTENT_TYPE)

    def test_to_stored_object_maps_s3_metadata(self) -> None:
        stored = util.to_stored_object("u1/a.pdf", {"ContentLength": 5, "ETag": '"abc"', "ContentType": "application/pdf"})
        self.assertEqual(stored.key, "u1/a.pdf")
        self.assertEqual(stored.size, 5)
        self.assertEqual(stored.etag, "abc")


if __name__ == "__main__":
    unittest.main()

