import os
import sys
from typing import Any, Optional
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "utils"))

from database_client import db

TABLE = "user_auth_data"
_UNSET: Any = object()


def is_admin_role(admin_value: Any) -> bool:
    if admin_value is None:
        return False
    return str(admin_value).strip().lower() == "admin"


def is_user_locked(lock_value: Any) -> bool:
    if lock_value is None:
        return False
    return str(lock_value).strip().lower() == "lock"


def _normalize_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_name": row["user_name"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "admin": row.get("admin"),
        "lock": row.get("lock"),
        "is_admin": is_admin_role(row.get("admin")),
        "is_locked": is_user_locked(row.get("lock")),
    }


async def get_user_by_email(email: str) -> Optional[dict]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number, admin, lock FROM {TABLE} WHERE email = $1",
        email,
    )


async def get_user_by_username(user_name: str) -> Optional[dict]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number, admin, lock FROM {TABLE} WHERE user_name = $1",
        user_name,
    )


async def get_user_by_phone(phone_number: str) -> Optional[dict]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number, admin, lock FROM {TABLE} WHERE phone_number = $1",
        phone_number,
    )


async def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    row = await db.fetch_one(
        f"SELECT id, user_name, email, phone_number, admin, lock FROM {TABLE} WHERE id = $1",
        user_id,
    )
    return _normalize_user(row) if row else None


async def get_user_auth_by_id(user_id: str) -> Optional[dict[str, Any]]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number, admin, lock FROM {TABLE} WHERE id = $1",
        user_id,
    )


async def create_user(
    user_name: str,
    hashed_password: str,
    email: str,
    phone_number: str,
    admin: Optional[str] = None,
    lock: Optional[str] = None,
) -> dict:
    user_id = str(uuid4())
    await db.execute(
        f"""
        INSERT INTO {TABLE} (id, user_name, password, email, phone_number, admin, lock)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        user_id,
        user_name,
        hashed_password,
        email,
        phone_number,
        admin,
        lock,
    )
    return {
        "id": user_id,
        "user_name": user_name,
        "email": email,
        "phone_number": phone_number,
        "admin": admin,
        "lock": lock,
        "is_admin": is_admin_role(admin),
        "is_locked": is_user_locked(lock),
    }


async def update_user(
    user_id: str,
    user_name: str,
    email: str,
    phone_number: str,
    hashed_password: str,
) -> None:
    await db.execute(
        f"""
        UPDATE {TABLE}
        SET user_name = $1, email = $2, phone_number = $3, password = $4
        WHERE id = $5
        """,
        user_name,
        email,
        phone_number,
        hashed_password,
        user_id,
    )


async def delete_user(user_id: str) -> str:
    return await db.execute(f"DELETE FROM {TABLE} WHERE id = $1", user_id)


async def update_password(email: str, hashed_password: str) -> None:
    await db.execute(
        f"UPDATE {TABLE} SET password = $1 WHERE email = $2",
        hashed_password, email,
    )


async def update_user_fields(
    user_id: str,
    *,
    user_name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    hashed_password: Optional[str] = None,
    admin: Any = _UNSET,
    lock: Any = _UNSET,
) -> None:
    sets: list[str] = []
    args: list[Any] = []

    if user_name is not None:
        args.append(user_name)
        sets.append(f"user_name = ${len(args)}")
    if email is not None:
        args.append(email)
        sets.append(f"email = ${len(args)}")
    if phone_number is not None:
        args.append(phone_number)
        sets.append(f"phone_number = ${len(args)}")
    if hashed_password is not None:
        args.append(hashed_password)
        sets.append(f"password = ${len(args)}")
    if admin is not _UNSET:
        args.append(admin)
        sets.append(f"admin = ${len(args)}")
    if lock is not _UNSET:
        args.append(lock)
        sets.append(f"lock = ${len(args)}")

    if not sets:
        return

    args.append(user_id)
    await db.execute(
        f"UPDATE {TABLE} SET {', '.join(sets)} WHERE id = ${len(args)}",
        *args,
    )
