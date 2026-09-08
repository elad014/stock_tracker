from typing import Any

from clients.database_client import db

USERS_TABLE = "user_auth_data"


async def list_users() -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"""
        SELECT id, user_name, email, phone_number, admin, lock
        FROM {USERS_TABLE}
        ORDER BY user_name
        """
    )
    return [
        {
            "id": str(row["id"]),
            "user_name": row["user_name"],
            "email": row["email"],
            "phone_number": row["phone_number"],
            "admin": row.get("admin"),
            "lock": row.get("lock"),
        }
        for row in rows
    ]
