import os
from typing import Any, Optional

import asyncpg
from dotenv import load_dotenv

load_dotenv()


class NeonClient:
    """PostgreSQL client for Neon using asyncpg direct connection."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._database_url = database_url or os.getenv("DATABASE_URL", "")
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=10,
                ssl="require",
            )
        return self._pool

    async def execute(self, sql: str, *params: Any) -> str:
        pool = await self._get_pool()
        return await pool.execute(sql, *params)

    async def fetch_one(self, sql: str, *params: Any) -> Optional[dict]:
        pool = await self._get_pool()
        row = await pool.fetchrow(sql, *params)
        return dict(row) if row else None

    async def fetch_all(self, sql: str, *params: Any) -> list[dict]:
        pool = await self._get_pool()
        rows = await pool.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
