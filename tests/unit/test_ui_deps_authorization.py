from types import SimpleNamespace
import unittest

from test_support import import_project_module

ui_deps = import_project_module("deps", "common", "ui_service/backend")
HTTPException = ui_deps.HTTPException


class UiAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.by_id: dict[str, dict] = {}
        self.by_email: dict[str, dict] = {}
        ui_deps.get_user_auth_by_id = lambda user_id: self._get_by_id(user_id)
        ui_deps.get_user_by_email = lambda email: self._get_by_email(email)
        ui_deps.jwt.decode = lambda token, *_args, **_kwargs: token

    async def _get_by_id(self, user_id: str):
        return self.by_id.get(user_id)

    async def _get_by_email(self, email: str):
        return self.by_email.get(email)

    async def test_get_current_user_rejects_missing_bearer_credentials(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            await ui_deps.get_current_user(None)
        self.assertEqual(caught.exception.status_code, 401)

    async def test_get_current_user_rejects_reset_token(self) -> None:
        credentials = SimpleNamespace(scheme="Bearer", credentials={"type": "reset", "sub": "a@example.com"})
        with self.assertRaises(HTTPException) as caught:
            await ui_deps.get_current_user(credentials)
        self.assertEqual(caught.exception.status_code, 401)

    async def test_get_current_user_falls_back_to_email_and_stringifies_id(self) -> None:
        self.by_email["a@example.com"] = {"id": 123, "email": "a@example.com", "lock": None, "admin": None}
        credentials = SimpleNamespace(scheme="Bearer", credentials={"sub": "a@example.com"})

        user = await ui_deps.get_current_user(credentials)

        self.assertEqual(user["id"], "123")

    async def test_get_current_user_rejects_locked_account(self) -> None:
        self.by_id["u1"] = {"id": "u1", "lock": "lock", "admin": None}
        credentials = SimpleNamespace(scheme="Bearer", credentials={"user_id": "u1"})

        with self.assertRaises(HTTPException) as caught:
            await ui_deps.get_current_user(credentials)
        self.assertEqual(caught.exception.status_code, 403)

    async def test_require_admin_allows_only_admin_role(self) -> None:
        self.assertEqual(await ui_deps.require_admin({"admin": "Admin"}), {"admin": "Admin"})
        with self.assertRaises(HTTPException) as caught:
            await ui_deps.require_admin({"admin": None})
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
