from types import SimpleNamespace
import unittest

from test_support import import_project_module

auth_service = import_project_module(
    "services.auth_service",
    "common",
    "ui_service/backend",
    model_stubs=True,
)
HTTPException = auth_service.HTTPException


class FakeLimiter:
    def __init__(self) -> None:
        self.allowed: list[str] = []
        self.recorded: list[str] = []
        self.reset_keys: list[str] = []

    def assert_allowed(self, key: str) -> None:
        self.allowed.append(key)

    def record(self, key: str) -> None:
        self.recorded.append(key)

    def reset(self, key: str) -> None:
        self.reset_keys.append(key)


class AuthServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.limiters = [FakeLimiter() for _ in range(5)]
        (
            auth_service.login_by_email,
            auth_service.login_by_ip,
            auth_service.register_by_ip,
            auth_service.reset_by_email,
            auth_service.reset_by_ip,
        ) = self.limiters
        self.users_by_email: dict[str, dict] = {}
        self.users_by_name: dict[str, dict] = {}
        self.users_by_phone: dict[str, dict] = {}
        self.created: dict | None = None
        auth_service.get_user_by_email = self.get_user_by_email
        auth_service.get_user_by_username = self.get_user_by_username
        auth_service.get_user_by_phone = self.get_user_by_phone
        auth_service.create_user = self.create_user
        auth_service.update_password = self.update_password
        auth_service.update_user_fields = self.update_user_fields
        auth_service.hash_password = lambda password: f"hashed:{password}"
        auth_service.verify_password = lambda plain, hashed: hashed == f"hashed:{plain}"
        auth_service.create_token = lambda data, minutes: f"token:{data['sub']}:{minutes}"
        self.password_updates: list[tuple[str, str]] = []
        self.field_updates: list[tuple[str, dict]] = []
        self.sent_resets: list[tuple[str, str]] = []
        self.sent_changes: list[tuple[str, list[dict[str, str]]]] = []
        auth_service.mailer = SimpleNamespace(
            send_password_reset=self.send_password_reset,
            send_account_changes=self.send_account_changes,
        )

    async def get_user_by_email(self, email: str):
        return self.users_by_email.get(email)

    async def get_user_by_username(self, user_name: str):
        return self.users_by_name.get(user_name)

    async def get_user_by_phone(self, phone: str):
        return self.users_by_phone.get(phone)

    async def create_user(self, **kwargs):
        self.created = kwargs
        return {"id": "u1", **kwargs, "is_admin": False, "is_locked": False}

    async def update_password(self, email: str, hashed: str) -> None:
        self.password_updates.append((email, hashed))

    async def update_user_fields(self, user_id: str, **kwargs) -> None:
        self.field_updates.append((user_id, kwargs))

    async def send_password_reset(self, to: str, reset_token: str):
        self.sent_resets.append((to, reset_token))
        return {}

    async def send_account_changes(self, to: str, changes: list[dict[str, str]]):
        self.sent_changes.append((to, changes))
        return {}

    async def test_register_creates_user_after_duplicate_checks(self) -> None:
        req = SimpleNamespace(user_name="alice", email="a@example.com", password="Pass1234", phone_number="050")

        response = await auth_service.register(req, "1.2.3.4")

        self.assertEqual(response.id, "u1")
        self.assertEqual(self.created["hashed_password"], "hashed:Pass1234")
        self.assertEqual(self.limiters[2].recorded, ["1.2.3.4"])

    async def test_register_rejects_duplicate_email(self) -> None:
        self.users_by_email["a@example.com"] = {"id": "existing"}
        req = SimpleNamespace(user_name="alice", email="a@example.com", password="Pass1234", phone_number="050")

        with self.assertRaises(HTTPException) as caught:
            await auth_service.register(req, "1.2.3.4")

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIsNone(self.created)

    async def test_login_success_resets_email_limiter_and_returns_bearer_token(self) -> None:
        self.users_by_email["a@example.com"] = {
            "id": "u1",
            "email": "a@example.com",
            "password": "hashed:Pass1234",
            "lock": None,
        }
        req = SimpleNamespace(email="a@example.com", password="Pass1234")

        token = await auth_service.login(req, "ip")

        self.assertEqual(token.token_type, "bearer")
        self.assertIn("a@example.com", token.access_token)
        self.assertEqual(self.limiters[0].reset_keys, ["a@example.com"])

    async def test_login_failure_records_email_and_ip_attempts(self) -> None:
        req = SimpleNamespace(email="A@EXAMPLE.COM", password="wrong")

        with self.assertRaises(HTTPException) as caught:
            await auth_service.login(req, "ip")

        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(self.limiters[0].recorded, ["a@example.com"])
        self.assertEqual(self.limiters[1].recorded, ["ip"])

    async def test_login_locked_user_is_forbidden(self) -> None:
        self.users_by_email["a@example.com"] = {
            "id": "u1",
            "email": "a@example.com",
            "password": "hashed:Pass1234",
            "lock": "lock",
        }

        with self.assertRaises(HTTPException) as caught:
            await auth_service.login(SimpleNamespace(email="a@example.com", password="Pass1234"), "ip")

        self.assertEqual(caught.exception.status_code, 403)

    async def test_update_me_rejects_wrong_current_password(self) -> None:
        current = {"id": "u1", "user_name": "alice", "email": "a@example.com", "phone_number": "050", "password": "hashed:old"}
        req = SimpleNamespace(user_name=None, email=None, phone_number=None, old_password="bad", new_password="Newpass1")

        with self.assertRaises(HTTPException) as caught:
            await auth_service.update_me(req, current)

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.field_updates, [])

    async def test_update_me_updates_email_and_returns_fresh_token(self) -> None:
        current = {"id": "u1", "user_name": "alice", "email": "old@example.com", "phone_number": "050", "password": "hashed:old"}
        req = SimpleNamespace(user_name="alice", email="new@example.com", phone_number="050", old_password=None, new_password=None)

        response = await auth_service.update_me(req, current)

        self.assertEqual(response.email, "new@example.com")
        self.assertIsNotNone(response.access_token)
        self.assertEqual(self.field_updates[0][1]["email"], "new@example.com")
        self.assertEqual({item[0] for item in self.sent_changes}, {"old@example.com", "new@example.com"})

    async def test_password_reset_request_does_not_reveal_unknown_email(self) -> None:
        response = await auth_service.password_reset_request(SimpleNamespace(email="missing@example.com"), "ip")

        self.assertEqual(response.message, "If the email exists, a reset link has been sent")
        self.assertEqual(self.sent_resets, [])

    async def test_password_reset_confirm_updates_known_unlocked_user(self) -> None:
        auth_service.jwt.decode = lambda *_args, **_kwargs: {"type": "reset", "sub": "a@example.com"}
        self.users_by_email["a@example.com"] = {"email": "a@example.com", "lock": None}

        response = await auth_service.password_reset_confirm(SimpleNamespace(token="reset", new_password="Nextpass1"))

        self.assertEqual(response.message, "Password has been reset successfully")
        self.assertEqual(self.password_updates, [("a@example.com", "hashed:Nextpass1")])

    async def test_invalid_reset_token_does_not_update_password(self) -> None:
        """Reject invalid reset token without changing a password."""
        auth_service.jwt.decode = lambda *_args, **_kwargs: (_ for _ in ()).throw(auth_service.JWTError("bad token"))

        with self.assertRaises(HTTPException) as caught:
            await auth_service.password_reset_confirm(SimpleNamespace(token="bad", new_password="Nextpass1"))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.password_updates, [])

    async def test_access_token_cannot_be_used_as_reset_token(self) -> None:
        """Reject an access token submitted to the password reset endpoint."""
        auth_service.jwt.decode = lambda *_args, **_kwargs: {"sub": "a@example.com", "user_id": "u1"}
        self.users_by_email["a@example.com"] = {"email": "a@example.com", "lock": None}

        with self.assertRaises(HTTPException) as caught:
            await auth_service.password_reset_confirm(SimpleNamespace(token="access", new_password="Nextpass1"))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.password_updates, [])

    async def test_locked_user_password_reset_request_does_not_send_email_or_reveal_account(self) -> None:
        """Do not reveal or email locked accounts during password reset request."""
        self.users_by_email["a@example.com"] = {"email": "a@example.com", "lock": "lock"}

        response = await auth_service.password_reset_request(SimpleNamespace(email="a@example.com"), "ip")

        self.assertEqual(response.message, "If the email exists, a reset link has been sent")
        self.assertEqual(self.sent_resets, [])

    async def test_locked_user_password_reset_confirm_is_rejected(self) -> None:
        """Reject reset confirmation for a locked account."""
        auth_service.jwt.decode = lambda *_args, **_kwargs: {"type": "reset", "sub": "a@example.com"}
        self.users_by_email["a@example.com"] = {"email": "a@example.com", "lock": "lock"}

        with self.assertRaises(HTTPException) as caught:
            await auth_service.password_reset_confirm(SimpleNamespace(token="reset", new_password="Nextpass1"))

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.password_updates, [])

if __name__ == "__main__":
    unittest.main()

