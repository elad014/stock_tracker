import unittest

from test_support import add_project_paths

add_project_paths()

from ui_utils.user_validators import (  # noqa: E402
    normalize_admin_role,
    normalize_lock_status,
    validate_password,
    validate_username,
)


class UserValidatorTests(unittest.TestCase):
    def test_validate_password_accepts_strong_password(self) -> None:
        self.assertEqual(validate_password("StrongPass1"), "StrongPass1")

    def test_validate_password_rejects_invalid_passwords(self) -> None:
        cases = [
            ("Short1", "at least 8 characters"),
            ("lowercase1", "uppercase"),
            ("UPPERCASE1", "lowercase"),
            ("NoDigitsHere", "digit"),
        ]
        for password, expected_message in cases:
            with self.subTest(password=password):
                with self.assertRaisesRegex(ValueError, expected_message):
                    validate_password(password)

    def test_validate_username_accepts_three_or_more_characters(self) -> None:
        self.assertEqual(validate_username("bob"), "bob")

    def test_validate_username_rejects_short_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 3 characters"):
            validate_username("ab")

    def test_normalize_admin_role(self) -> None:
        self.assertEqual(normalize_admin_role(" Admin "), "admin")
        self.assertIsNone(normalize_admin_role(""))
        self.assertIsNone(normalize_admin_role(None))
        self.assertIsNone(normalize_admin_role(True))
        with self.assertRaisesRegex(ValueError, "empty or 'admin'"):
            normalize_admin_role("owner")

    def test_normalize_lock_status(self) -> None:
        self.assertEqual(normalize_lock_status(" Lock "), "lock")
        self.assertIsNone(normalize_lock_status(""))
        self.assertIsNone(normalize_lock_status(None))
        self.assertIsNone(normalize_lock_status(False))
        with self.assertRaisesRegex(ValueError, "empty or 'lock'"):
            normalize_lock_status("blocked")


if __name__ == "__main__":
    unittest.main()
