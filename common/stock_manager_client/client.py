from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from constant import INTERNAL_API_KEY, INTERNAL_API_KEY_HEADER, STOCK_MANAGER_URL


class StockManagerClient:
    """HTTP client for the internal stock-manager service."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or STOCK_MANAGER_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else INTERNAL_API_KEY

    def _headers(self) -> dict[str, str]:
        return {INTERNAL_API_KEY_HEADER: self._api_key}

    def _raise_from_response(self, response: httpx.Response) -> None:
        detail: Any
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except Exception:
            detail = response.text or "Stock manager request failed"
        raise HTTPException(response.status_code, detail)

    def _json_response(self, response: httpx.Response, expected_type: type) -> Any:
        try:
            payload = response.json()
        except Exception as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Stock manager returned invalid JSON",
            ) from exc
        if not isinstance(payload, expected_type):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Stock manager returned an invalid response",
            )
        return payload

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        expected_type: type,
        **kwargs: Any,
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._headers(),
                    **kwargs,
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach stock manager",
            ) from exc
        if response.status_code >= 400:
            self._raise_from_response(response)
        return self._json_response(response, expected_type)

    async def list_watchlist(self, user_id: str) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            f"/watchlist/{user_id}",
            timeout=30.0,
            expected_type=list,
        )

    async def list_stocks(self) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            "/stocks",
            timeout=30.0,
            expected_type=list,
        )

    async def get_stock(self, stock_id: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/stocks/{stock_id}",
            timeout=30.0,
            expected_type=dict,
        )

    async def get_stock_history(
        self,
        stock_id: str,
        range_key: str = "1Y",
    ) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            f"/stocks/{stock_id}/history",
            timeout=60.0,
            expected_type=list,
            params={"range": range_key},
        )

    async def get_stock_summery(self, stock_id: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/stocks/{stock_id}/summary",
            timeout=30.0,
            expected_type=dict,
        )

    async def update_stock_summery(
        self,
        stock_id: str,
        stock_summery: Optional[str],
        *,
        stock_news_published_at: Optional[str] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "stock_summery": stock_summery,
            "stock_news_published_at": stock_news_published_at,
        }
        return await self._request_json(
            "PUT",
            f"/stocks/{stock_id}/summary",
            timeout=30.0,
            expected_type=dict,
            json=body,
        )

    async def get_stock_by_symbol(self, symbol: str) -> Optional[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._base_url}/stocks/symbol/{symbol}",
                    headers=self._headers(),
                )
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Failed to reach stock manager",
            ) from exc
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.status_code >= 400:
            self._raise_from_response(response)
        return self._json_response(response, dict)

    async def is_on_watchlist(self, user_id: str, stock_id: str) -> bool:
        payload = await self._request_json(
            "GET",
            f"/watchlist/{user_id}/{stock_id}",
            timeout=30.0,
            expected_type=dict,
        )
        return bool(payload.get("on_watchlist"))

    async def add_to_watchlist(self, user_id: str, symbol: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/watchlist",
            timeout=120.0,
            expected_type=dict,
            json={"user_id": user_id, "symbol": symbol},
        )

    async def remove_from_watchlist(self, user_id: str, stock_id: str) -> dict[str, Any]:
        return await self._request_json(
            "DELETE",
            "/watchlist",
            timeout=30.0,
            expected_type=dict,
            json={"user_id": user_id, "stock_id": stock_id},
        )

    async def ensure_and_assign(self, user_id: str, symbol: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/admin/ensure-and-assign",
            timeout=120.0,
            expected_type=dict,
            json={"user_id": user_id, "symbol": symbol},
        )

    async def clear_user_watchlist(self, user_id: str) -> dict[str, Any]:
        return await self._request_json(
            "DELETE",
            f"/watchlist/user/{user_id}",
            timeout=30.0,
            expected_type=dict,
        )

    async def unwatch_stock_everywhere(self, stock_id: str) -> dict[str, Any]:
        return await self._request_json(
            "DELETE",
            f"/stocks/{stock_id}",
            timeout=30.0,
            expected_type=dict,
        )

    @staticmethod
    def quote_to_watchlist_stock(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(payload.get("stock_id") or payload.get("id")),
            "symbol": payload.get("symbol") or payload.get("name"),
            "price": (
                payload.get("close")
                if payload.get("close") is not None
                else payload.get("price")
            ),
            "change": (
                payload.get("change") if payload.get("change") is not None else None
            ),
            "stock_summery": payload.get("stock_summery"),
            "stock_news_published_at": payload.get("stock_news_published_at"),
        }


stock_manager_client = StockManagerClient()
