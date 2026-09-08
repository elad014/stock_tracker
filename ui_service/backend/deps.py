from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db_logics.user_db_logic import get_user_auth_by_id, get_user_by_email, is_admin_role, is_user_locked
from ui_utils.token_crypto import ACCESS_TOKEN_TYPE, TokenError, decode_token

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

    try:
        claims: dict[str, Any] = decode_token(credentials.credentials, ACCESS_TOKEN_TYPE)
    except TokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id: str | None = claims.get("user_id")
    email: str | None = claims.get("sub")

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

    if is_user_locked(user.get("lock")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Account is locked",
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
