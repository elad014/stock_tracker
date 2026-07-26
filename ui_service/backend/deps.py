import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from db_logics.user_db_logic import get_user_auth_by_id, get_user_by_email, is_admin_role

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
        user_id: str | None = payload.get("user_id")
        email: str | None = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = None
    if user_id:
        user = await get_user_auth_by_id(str(user_id))
    if not user and email:
        user = await get_user_by_email(email)
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user["id"] = str(user["id"])
    return user


async def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not is_admin_role(current_user.get("admin")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Admin access required",
        )
    return current_user
