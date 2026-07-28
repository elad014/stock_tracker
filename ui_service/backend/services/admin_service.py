from typing import Any

from fastapi import HTTPException, status

from services.auth_service import hash_password
from db_logics import admin_db_logic as admin_db
from db_logics import user_db_logic as user_db
from models.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminUpdateUserRequest,
    AdminUser,
    AssignStockRequest,
)
from models.auth import MessageResponse
from models.watchlist import AddWatchlistRequest, WatchlistStock
import stock_manager_client as stock_manager


async def _user_with_stocks(user: dict[str, Any]) -> AdminUser:
    stocks = await stock_manager.list_watchlist(user["id"])
    admin_value: str | None = user.get("admin")
    lock_value: str | None = user.get("lock")
    if admin_value is not None:
        admin_value = str(admin_value)
    if lock_value is not None:
        lock_value = str(lock_value)
    return AdminUser(
        id=str(user["id"]),
        user_name=user["user_name"],
        email=user["email"],
        phone_number=user["phone_number"],
        admin=admin_value if user_db.is_admin_role(admin_value) else None,
        lock=lock_value if user_db.is_user_locked(lock_value) else None,
        followed_stocks=[
            WatchlistStock(**stock_manager.quote_to_watchlist_stock(s)) for s in stocks
        ],
    )


async def list_users() -> list[AdminUser]:
    users = await admin_db.list_users()
    return [await _user_with_stocks(user) for user in users]


async def create_user(req: AdminCreateUserRequest) -> AdminUser:
    if await user_db.get_user_by_email(req.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if await user_db.get_user_by_username(req.user_name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    if await user_db.get_user_by_phone(req.phone_number):
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already registered")

    user = await user_db.create_user(
        user_name=req.user_name,
        hashed_password=hash_password(req.password),
        email=req.email,
        phone_number=req.phone_number,
        admin=req.admin,
        lock=req.lock,
    )
    return await _user_with_stocks(user)


async def update_user(user_id: str, req: AdminUpdateUserRequest) -> AdminUser:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    email_owner = await user_db.get_user_by_email(req.email)
    if email_owner and str(email_owner["id"]) != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    username_owner = await user_db.get_user_by_username(req.user_name)
    if username_owner and str(username_owner["id"]) != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    phone_owner = await user_db.get_user_by_phone(req.phone_number)
    if phone_owner and str(phone_owner["id"]) != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already registered")

    update_kwargs: dict[str, Any] = {
        "user_name": req.user_name,
        "email": req.email,
        "phone_number": req.phone_number,
    }
    if "admin" in req.model_fields_set:
        update_kwargs["admin"] = req.admin
    if "lock" in req.model_fields_set:
        update_kwargs["lock"] = req.lock

    await user_db.update_user_fields(user_id, **update_kwargs)

    updated = await user_db.get_user_by_id(user_id)
    assert updated is not None
    return await _user_with_stocks(updated)


async def set_user_password(user_id: str, req: AdminSetPasswordRequest) -> MessageResponse:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await user_db.update_user_fields(
        user_id,
        hashed_password=hash_password(req.new_password),
    )
    return MessageResponse(message="Password updated")


async def remove_user_admin(user_id: str) -> MessageResponse:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await user_db.update_user_fields(user_id, admin=None)
    return MessageResponse(message="Admin role removed")


async def remove_user_lock(user_id: str) -> MessageResponse:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await user_db.update_user_fields(user_id, lock=None)
    return MessageResponse(message="Lock removed")


async def delete_user(user_id: str) -> MessageResponse:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await stock_manager.clear_user_watchlist(user_id)
    result = await user_db.delete_user(user_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return MessageResponse(message="User deleted")


async def list_stocks() -> list[WatchlistStock]:
    rows = await stock_manager.list_stocks()
    return [WatchlistStock(**stock_manager.quote_to_watchlist_stock(row)) for row in rows]


async def create_stock(req: AddWatchlistRequest) -> WatchlistStock:
    existing = await stock_manager.get_stock_by_symbol(req.name)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock already exists")
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Stocks are created when assigned to a user watchlist. "
        "Use assign with a symbol, or add the ticker from a user watchlist.",
    )


async def delete_stock(stock_id: str) -> MessageResponse:
    await stock_manager.get_stock(stock_id)
    await stock_manager.unwatch_stock_everywhere(stock_id)
    return MessageResponse(
        message="Stock removed from all watchlists; cleanup will archive history"
    )


async def assign_stock_to_user(user_id: str, req: AssignStockRequest) -> WatchlistStock:
    user = await user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    symbol = req.symbol
    if not symbol and req.stock_id:
        stock = await stock_manager.get_stock(req.stock_id)
        if await stock_manager.is_on_watchlist(user_id, req.stock_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Stock already on user watchlist")
        symbol = stock["symbol"]

    if not symbol:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide stock_id or symbol",
        )

    payload = await stock_manager.ensure_and_assign(user_id, symbol)
    return WatchlistStock(**stock_manager.quote_to_watchlist_stock(payload))


async def remove_stock_from_user(user_id: str, stock_id: str) -> MessageResponse:
    user = await user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await stock_manager.remove_from_watchlist(user_id, stock_id)
    return MessageResponse(message="Stock removed from user watchlist")
