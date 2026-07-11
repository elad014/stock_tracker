from typing import Optional
from uuid import uuid4

from database import db

TABLE = "user_auth_data"


async def get_user_by_email(email: str) -> Optional[dict]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number FROM {TABLE} WHERE email = $1",
        email,
    )


async def get_user_by_username(user_name: str) -> Optional[dict]:
    return await db.fetch_one(
        f"SELECT id, user_name, password, email, phone_number FROM {TABLE} WHERE user_name = $1",
        user_name,
    )


async def create_user(user_name: str, hashed_password: str, email: str, phone_number: str) -> dict:
    user_id = str(uuid4())
    await db.execute(
        f"INSERT INTO {TABLE} (id, user_name, password, email, phone_number) VALUES ($1, $2, $3, $4, $5)",
        user_id, user_name, hashed_password, email, phone_number,
    )
    return {"id": user_id, "user_name": user_name, "email": email, "phone_number": phone_number}


async def update_password(email: str, hashed_password: str) -> None:
    await db.execute(
        f"UPDATE {TABLE} SET password = $1 WHERE email = $2",
        hashed_password, email,
    )
