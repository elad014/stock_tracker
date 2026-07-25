import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "utils"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "utils"))

from database_client import db

USERS_TABLE = "user_auth_data"


async def list_users() -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        f"SELECT id, user_name, email, phone_number FROM {USERS_TABLE} ORDER BY user_name"
    )
    return [
        {
            "id": str(row["id"]),
            "user_name": row["user_name"],
            "email": row["email"],
            "phone_number": row["phone_number"],
        }
        for row in rows
    ]
