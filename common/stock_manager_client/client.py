import os
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

STOCK_MANAGER_URL = os.getenv("STOCK_MANAGER_URL", "http://localhost:8001").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def _headers() -> dict[str, str]:
    return {"X-Internal-Api-Key": INTERNAL_API_KEY}


def _raise_from_response(response: httpx.Response) -> None:
    detail: Any
    try:
        payload = response.json()
        detail = payload.get("detail", payload)
    except Exception:
        detail = response.text or "Stock manager request failed"
    raise HTTPException(response.status_code, detail)


async def list_watchlist(user_id: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/watchlist/{user_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def list_stocks() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/stocks",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def get_stock(stock_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/stocks/{stock_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def get_stock_history(
    stock_id: str,
    range_key: str = "1Y",
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/stocks/{stock_id}/history",
            headers=_headers(),
            params={"range": range_key},
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def get_stock_summery(stock_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/stocks/{stock_id}/summary",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def update_stock_summery(
    stock_id: str,
    stock_summery: Optional[str],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.put(
            f"{STOCK_MANAGER_URL}/stocks/{stock_id}/summary",
            headers=_headers(),
            json={"stock_summery": stock_summery},
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def get_stock_by_symbol(symbol: str) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/stocks/symbol/{symbol}",
            headers=_headers(),
        )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        return None
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def is_on_watchlist(user_id: str, stock_id: str) -> bool:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{STOCK_MANAGER_URL}/watchlist/{user_id}/{stock_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    payload = response.json()
    return bool(payload.get("on_watchlist"))


async def add_to_watchlist(user_id: str, symbol: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{STOCK_MANAGER_URL}/watchlist",
            headers=_headers(),
            json={"user_id": user_id, "symbol": symbol},
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def remove_from_watchlist(user_id: str, stock_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            "DELETE",
            f"{STOCK_MANAGER_URL}/watchlist",
            headers=_headers(),
            json={"user_id": user_id, "stock_id": stock_id},
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def ensure_and_assign(user_id: str, symbol: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{STOCK_MANAGER_URL}/admin/ensure-and-assign",
            headers=_headers(),
            json={"user_id": user_id, "symbol": symbol},
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def clear_user_watchlist(user_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{STOCK_MANAGER_URL}/watchlist/user/{user_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


async def unwatch_stock_everywhere(stock_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.delete(
            f"{STOCK_MANAGER_URL}/stocks/{stock_id}",
            headers=_headers(),
        )
    if response.status_code >= 400:
        _raise_from_response(response)
    return response.json()


def quote_to_watchlist_stock(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(payload.get("stock_id") or payload.get("id")),
        "symbol": payload.get("symbol") or payload.get("name"),
        "price": (
            payload.get("close") if payload.get("close") is not None else payload.get("price")
        ),
        "change": (
            payload.get("change") if payload.get("change") is not None else None
        ),
        "stock_summery": payload.get("stock_summery"),
    }
