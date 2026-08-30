from types import SimpleNamespace
import unittest

from test_support import import_project_module


def request_from(ip: str = "127.0.0.1") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip))


class InMemoryAuthDb:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.by_email: dict[str, str] = {}
        self.by_name: dict[str, str] = {}
        self.by_phone: dict[str, str] = {}
        self.next_id = 1
        self.deleted: list[str] = []
        self.updated_fields: list[tuple[str, dict]] = []

    def _store(self, user: dict) -> dict:
        self.users[user["id"]] = user
        self.by_email[user["email"]] = user["id"]
        self.by_name[user["user_name"]] = user["id"]
        self.by_phone[user["phone_number"]] = user["id"]
        return user

    async def create_user(self, user_name, hashed_password, email, phone_number, admin=None, lock=None):
        user = {
            "id": f"u{self.next_id}",
            "user_name": user_name,
            "password": hashed_password,
            "email": email,
            "phone_number": phone_number,
            "admin": admin,
            "lock": lock,
            "is_admin": str(admin).lower() == "admin" if admin else False,
            "is_locked": str(lock).lower() == "lock" if lock else False,
        }
        self.next_id += 1
        return self._store(user)

    async def get_user_by_email(self, email):
        user_id = self.by_email.get(email)
        return self.users.get(user_id) if user_id else None

    async def get_user_by_username(self, user_name):
        user_id = self.by_name.get(user_name)
        return self.users.get(user_id) if user_id else None

    async def get_user_by_phone(self, phone_number):
        user_id = self.by_phone.get(phone_number)
        return self.users.get(user_id) if user_id else None

    async def get_user_by_id(self, user_id):
        user = self.users.get(user_id)
        if not user:
            return None
        return {k: v for k, v in user.items() if k != "password"}

    async def update_password(self, email, hashed_password):
        user = await self.get_user_by_email(email)
        user["password"] = hashed_password

    async def update_user_fields(self, user_id, **kwargs):
        self.updated_fields.append((user_id, kwargs))
        user = self.users[user_id]
        for key, value in kwargs.items():
            if value is not None or key in {"admin", "lock"}:
                if key == "hashed_password":
                    user["password"] = value
                else:
                    user[key] = value
        self.by_email = {u["email"]: uid for uid, u in self.users.items()}
        self.by_name = {u["user_name"]: uid for uid, u in self.users.items()}
        self.by_phone = {u["phone_number"]: uid for uid, u in self.users.items()}

    async def delete_user(self, user_id):
        if user_id not in self.users:
            return "DELETE 0"
        self.deleted.append(user_id)
        user = self.users.pop(user_id)
        self.by_email.pop(user["email"], None)
        self.by_name.pop(user["user_name"], None)
        self.by_phone.pop(user["phone_number"], None)
        return "DELETE 1"

    async def list_users(self):
        return [{k: v for k, v in user.items() if k != "password"} for user in sorted(self.users.values(), key=lambda row: row["user_name"])]


class NoopLimiter:
    def assert_allowed(self, key):
        pass
    def record(self, key):
        pass
    def reset(self, key):
        pass


class AuthenticationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "AUTHENTICATION"

    async def asyncSetUp(self) -> None:
        self.auth_routes = import_project_module("routers.auth_routes", "common", "ui_service/backend", model_stubs=True)
        self.auth_service = self.auth_routes.auth_service
        self.db = InMemoryAuthDb()
        self.auth_service.get_user_by_email = self.db.get_user_by_email
        self.auth_service.get_user_by_username = self.db.get_user_by_username
        self.auth_service.get_user_by_phone = self.db.get_user_by_phone
        self.auth_service.create_user = self.db.create_user
        self.auth_service.update_password = self.db.update_password
        self.auth_service.update_user_fields = self.db.update_user_fields
        self.auth_service.hash_password = lambda password: f"hashed:{password}"
        self.auth_service.verify_password = lambda plain, hashed: hashed == f"hashed:{plain}"
        self.auth_service.create_token = lambda data, minutes: f"token:{data['sub']}:{data.get('user_id', '')}:{minutes}"
        self.auth_service.jwt.decode = lambda token, *_args, **_kwargs: token if isinstance(token, dict) else {"type": "reset", "sub": token.replace("reset:", "")}
        limiter = NoopLimiter()
        self.auth_service.login_by_email = limiter
        self.auth_service.login_by_ip = limiter
        self.auth_service.register_by_ip = limiter
        self.auth_service.reset_by_email = limiter
        self.auth_service.reset_by_ip = limiter
        self.sent_resets: list[str] = []
        self.sent_changes: list[str] = []
        self.auth_service.mailer = SimpleNamespace(
            send_password_reset=self.send_reset,
            send_account_changes=self.send_changes,
        )

    async def send_reset(self, to, reset_token):
        self.sent_resets.append(to)
        return {}

    async def send_changes(self, to, changes):
        self.sent_changes.append(to)
        return {}

    async def test_user_registration_valid_user_can_register(self) -> None:
        response = await self.auth_routes.register(SimpleNamespace(user_name="alice", email="alice@example.com", password="Password1", phone_number="050"), request_from())
        self.assertEqual(response.email, "alice@example.com")
        self.assertEqual(self.db.users["u1"]["password"], "hashed:Password1")

    async def test_user_registration_duplicate_email_rejected(self) -> None:
        await self.db.create_user("alice", "hashed:Password1", "alice@example.com", "050")
        with self.assertRaises(self.auth_service.HTTPException) as caught:
            await self.auth_routes.register(SimpleNamespace(user_name="other", email="alice@example.com", password="Password1", phone_number="051"), request_from())
        self.assertEqual(caught.exception.status_code, 409)

    async def test_login_correct_credentials_returns_access_token(self) -> None:
        await self.db.create_user("alice", "hashed:Password1", "alice@example.com", "050")
        response = await self.auth_routes.login(SimpleNamespace(email="alice@example.com", password="Password1"), request_from())
        self.assertEqual(response.token_type, "bearer")
        self.assertIn("alice@example.com", response.access_token)

    async def test_login_incorrect_password_rejected(self) -> None:
        await self.db.create_user("alice", "hashed:Password1", "alice@example.com", "050")
        with self.assertRaises(self.auth_service.HTTPException) as caught:
            await self.auth_routes.login(SimpleNamespace(email="alice@example.com", password="bad"), request_from())
        self.assertEqual(caught.exception.status_code, 401)

    async def test_login_locked_user_is_forbidden(self) -> None:
        await self.db.create_user("alice", "hashed:Password1", "alice@example.com", "050", lock="lock")
        with self.assertRaises(self.auth_service.HTTPException) as caught:
            await self.auth_routes.login(SimpleNamespace(email="alice@example.com", password="Password1"), request_from())
        self.assertEqual(caught.exception.status_code, 403)

    async def test_password_reset_request_sends_mail_for_known_unlocked_user(self) -> None:
        await self.db.create_user("alice", "hashed:Password1", "alice@example.com", "050")
        response = await self.auth_routes.password_reset_request(SimpleNamespace(email="alice@example.com"), request_from())
        self.assertIn("reset link", response.message)
        self.assertEqual(self.sent_resets, ["alice@example.com"])

    async def test_password_reset_confirm_changes_password(self) -> None:
        await self.db.create_user("alice", "hashed:Oldpass1", "alice@example.com", "050")
        await self.auth_routes.password_reset_confirm(SimpleNamespace(token="reset:alice@example.com", new_password="Newpass1"))
        self.assertEqual(self.db.users["u1"]["password"], "hashed:Newpass1")

    async def test_profile_settings_update_changes_email_and_sends_notifications(self) -> None:
        user = await self.db.create_user("alice", "hashed:Password1", "old@example.com", "050")
        response = await self.auth_routes.update_me(SimpleNamespace(user_name="alice2", email="new@example.com", phone_number="051", old_password=None, new_password=None), user)
        self.assertEqual(response.email, "new@example.com")
        self.assertEqual(response.user_name, "alice2")
        self.assertEqual(set(self.sent_changes), {"old@example.com", "new@example.com"})


class AdminIntegrationTests(unittest.IsolatedAsyncioTestCase):
    COMPONENT = "ADMINISTRATION"

    async def asyncSetUp(self) -> None:
        self.admin_routes = import_project_module("routers.admin_routes", "common", "ui_service/backend", model_stubs=True)
        self.admin_service = self.admin_routes.admin_service
        self.db = InMemoryAuthDb()
        await self.db.create_user("admin", "hashed:Adminpass1", "admin@example.com", "050", admin="admin")
        await self.db.create_user("user", "hashed:Userpass1", "user@example.com", "051")
        self.admin_service.user_db = SimpleNamespace(
            is_admin_role=lambda value: str(value).strip().lower() == "admin" if value else False,
            is_user_locked=lambda value: str(value).strip().lower() == "lock" if value else False,
            get_user_by_id=self.db.get_user_by_id,
            get_user_by_email=self.db.get_user_by_email,
            get_user_by_username=self.db.get_user_by_username,
            get_user_by_phone=self.db.get_user_by_phone,
            create_user=self.db.create_user,
            update_user_fields=self.db.update_user_fields,
            delete_user=self.db.delete_user,
        )
        self.admin_service.admin_db = SimpleNamespace(list_users=self.db.list_users)
        self.admin_service.hash_password = lambda password: f"hashed:{password}"
        self.cleaned: list[str] = []
        self.admin_service.documents_service = SimpleNamespace(delete_all_user_files=lambda user_id: self._record("documents", user_id))
        self.admin_service.doc_agent = SimpleNamespace(purge_user=lambda user_id: self._record("doc-agent", user_id))
        self.admin_service.stock_manager = SimpleNamespace(
            list_watchlist=lambda user_id: self._async([]),
            quote_to_watchlist_stock=lambda row: {"id": row.get("stock_id"), "symbol": row.get("symbol"), "price": row.get("close"), "change": row.get("change")},
            clear_user_watchlist=lambda user_id: self._record("watchlist", user_id),
            get_stock=lambda stock_id: self._async({"stock_id": stock_id, "symbol": "AAPL"}),
            get_stock_by_symbol=lambda symbol: self._async(None),
            is_on_watchlist=lambda user_id, stock_id: self._async(False),
            ensure_and_assign=lambda user_id, symbol: self._async({"stock_id": "s1", "symbol": symbol.upper(), "close": 100, "change": 1}),
            unwatch_stock_everywhere=lambda stock_id: self._record("unwatch", stock_id),
            remove_from_watchlist=lambda user_id, stock_id: self._record("remove", stock_id),
        )

    async def _async(self, value):
        return value

    async def _record(self, kind, value):
        self.cleaned.append(f"{kind}:{value}")
        return {}

    async def test_admin_authorization_rejects_non_admin_user(self) -> None:
        deps = import_project_module("deps", "common", "ui_service/backend")
        with self.assertRaises(deps.HTTPException) as caught:
            await deps.require_admin({"admin": None})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_admin_lists_users_through_admin_route(self) -> None:
        users = await self.admin_routes.list_users()
        self.assertEqual([user.email for user in users], ["admin@example.com", "user@example.com"])

    async def test_admin_creates_user_with_hashed_password(self) -> None:
        response = await self.admin_routes.create_user(SimpleNamespace(user_name="new", email="new@example.com", phone_number="052", password="Password1", admin=None, lock=None))
        self.assertEqual(response.email, "new@example.com")
        self.assertEqual((await self.db.get_user_by_email("new@example.com"))["password"], "hashed:Password1")

    async def test_admin_locks_and_unlocks_user_profile(self) -> None:
        response = await self.admin_routes.update_user("u2", SimpleNamespace(user_name="user", email="user@example.com", phone_number="051", admin=None, lock="lock", model_fields_set={"lock"}))
        self.assertEqual(response.lock, "lock")
        unlock = await self.admin_routes.remove_user_lock("u2")
        self.assertEqual(unlock.message, "Lock removed")
        self.assertIsNone((await self.db.get_user_by_id("u2"))["lock"])

    async def test_admin_assigns_stock_to_user(self) -> None:
        response = await self.admin_routes.assign_stock_to_user("u2", SimpleNamespace(symbol="aapl", stock_id=None))
        self.assertEqual(response.symbol, "AAPL")

    async def test_admin_deletes_user_and_runs_cleanup_steps(self) -> None:
        response = await self.admin_routes.delete_user("u2")
        self.assertEqual(response.message, "User deleted")
        self.assertEqual(self.cleaned[:3], ["documents:u2", "doc-agent:u2", "watchlist:u2"])
        self.assertIsNone(await self.db.get_user_by_id("u2"))


if __name__ == "__main__":
    unittest.main()
