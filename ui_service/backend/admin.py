from typing import Any

import bcrypt
from fastapi import APIRouter, HTTPException, status

from db_logics import admin_db_logic as admin_db
from db_logics import user_db_logic as user_db
from db_logics import watchlist_db_logic as watchlist_db
from models import (
    AddWatchlistRequest,
    AdminUser,
    AssignStockRequest,
    MessageResponse,
    RegisterRequest,
    WatchlistStock,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def _user_with_stocks(user: dict[str, Any]) -> AdminUser:
    stocks = await watchlist_db.get_watchlist(user["id"])
    return AdminUser(
        id=str(user["id"]),
        user_name=user["user_name"],
        email=user["email"],
        phone_number=user["phone_number"],
        followed_stocks=[WatchlistStock(**s) for s in stocks],
    )


@router.get("/users", response_model=list[AdminUser])
async def list_users() -> list[AdminUser]:
    users = await admin_db.list_users()
    return [await _user_with_stocks(user) for user in users]


@router.post("/users", response_model=AdminUser, status_code=status.HTTP_201_CREATED)
async def create_user(req: RegisterRequest) -> AdminUser:
    if await user_db.get_user_by_email(req.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if await user_db.get_user_by_username(req.user_name):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    user = await user_db.create_user(
        user_name=req.user_name,
        hashed_password=_hash_password(req.password),
        email=req.email,
        phone_number=req.phone_number,
    )
    return await _user_with_stocks(user)


@router.put("/users/{user_id}", response_model=AdminUser)
async def update_user(user_id: str, req: RegisterRequest) -> AdminUser:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    email_owner = await user_db.get_user_by_email(req.email)
    if email_owner and str(email_owner["id"]) != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    username_owner = await user_db.get_user_by_username(req.user_name)
    if username_owner and str(username_owner["id"]) != user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    await user_db.update_user(
        user_id=user_id,
        user_name=req.user_name,
        email=req.email,
        phone_number=req.phone_number,
        hashed_password=_hash_password(req.password),
    )
    updated = await user_db.get_user_by_id(user_id)
    assert updated is not None
    return await _user_with_stocks(updated)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(user_id: str) -> MessageResponse:
    existing = await user_db.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await watchlist_db.delete_watchlist_for_user(user_id)
    result = await user_db.delete_user(user_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return MessageResponse(message="User deleted")


@router.get("/stocks", response_model=list[WatchlistStock])
async def list_stocks() -> list[WatchlistStock]:
    rows = await watchlist_db.list_stocks()
    return [WatchlistStock(**row) for row in rows]


@router.post("/stocks", response_model=WatchlistStock, status_code=status.HTTP_201_CREATED)
async def create_stock(req: AddWatchlistRequest) -> WatchlistStock:
    existing = await watchlist_db.get_stock_by_name(req.name)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock already exists")
    stock = await watchlist_db.create_stock(req.name)
    return WatchlistStock(**stock)


@router.delete("/stocks/{stock_id}", response_model=MessageResponse)
async def delete_stock(stock_id: str) -> MessageResponse:
    existing = await watchlist_db.get_stock_by_id(stock_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")

    await watchlist_db.delete_watchlist_for_stock(stock_id)
    result = await watchlist_db.delete_stock(stock_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")
    return MessageResponse(message="Stock deleted")


@router.post(
    "/users/{user_id}/watchlist",
    response_model=WatchlistStock,
    status_code=status.HTTP_201_CREATED,
)
async def assign_stock_to_user(user_id: str, req: AssignStockRequest) -> WatchlistStock:
    user = await user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    stock = await watchlist_db.get_stock_by_id(req.stock_id)
    if not stock:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not found")

    if await watchlist_db.is_on_watchlist(user_id, req.stock_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock already on user watchlist")

    await watchlist_db.add_to_watchlist(user_id, req.stock_id)
    return WatchlistStock(**stock)


@router.delete(
    "/users/{user_id}/watchlist/{stock_id}",
    response_model=MessageResponse,
)
async def remove_stock_from_user(user_id: str, stock_id: str) -> MessageResponse:
    user = await user_db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    result = await watchlist_db.remove_from_watchlist(user_id, stock_id)
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stock not on user watchlist")
    return MessageResponse(message="Stock removed from user watchlist")
