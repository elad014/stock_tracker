from fastapi import APIRouter, Depends, status

import services.admin_service as admin_service
from deps import require_admin
from models.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminUpdateUserRequest,
    AdminUser,
    AssignStockRequest,
    CreateAdminStockRequest,
)
from models.auth import MessageResponse
from models.watchlist import WatchlistStock

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/users", response_model=list[AdminUser])
async def list_users() -> list[AdminUser]:
    return await admin_service.list_users()


@router.post("/users", response_model=AdminUser, status_code=status.HTTP_201_CREATED)
async def create_user(req: AdminCreateUserRequest) -> AdminUser:
    return await admin_service.create_user(req)


@router.put("/users/{user_id}", response_model=AdminUser)
async def update_user(user_id: str, req: AdminUpdateUserRequest) -> AdminUser:
    return await admin_service.update_user(user_id, req)


@router.put("/users/{user_id}/password", response_model=MessageResponse)
async def set_user_password(user_id: str, req: AdminSetPasswordRequest) -> MessageResponse:
    return await admin_service.set_user_password(user_id, req)


@router.delete("/users/{user_id}/admin", response_model=MessageResponse)
async def remove_user_admin(user_id: str) -> MessageResponse:
    return await admin_service.remove_user_admin(user_id)


@router.delete("/users/{user_id}/lock", response_model=MessageResponse)
async def remove_user_lock(user_id: str) -> MessageResponse:
    return await admin_service.remove_user_lock(user_id)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(user_id: str) -> MessageResponse:
    return await admin_service.delete_user(user_id)


@router.get("/stocks", response_model=list[WatchlistStock])
async def list_stocks() -> list[WatchlistStock]:
    return await admin_service.list_stocks()


@router.post("/stocks", response_model=WatchlistStock, status_code=status.HTTP_201_CREATED)
async def create_stock(req: CreateAdminStockRequest) -> WatchlistStock:
    return await admin_service.create_stock(req)


@router.delete("/stocks/{stock_id}", response_model=MessageResponse)
async def delete_stock(stock_id: str) -> MessageResponse:
    return await admin_service.delete_stock(stock_id)


@router.post(
    "/users/{user_id}/watchlist",
    response_model=WatchlistStock,
    status_code=status.HTTP_201_CREATED,
)
async def assign_stock_to_user(user_id: str, req: AssignStockRequest) -> WatchlistStock:
    return await admin_service.assign_stock_to_user(user_id, req)


@router.delete(
    "/users/{user_id}/watchlist/{stock_id}",
    response_model=MessageResponse,
)
async def remove_stock_from_user(user_id: str, stock_id: str) -> MessageResponse:
    return await admin_service.remove_stock_from_user(user_id, stock_id)
