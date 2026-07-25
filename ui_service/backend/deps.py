import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from db_logics.user_db_logic import get_user_by_email

load_dotenv()

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token: str = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "reset":
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        email: str | None = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not email:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user["id"] = str(user["id"])
    return user
