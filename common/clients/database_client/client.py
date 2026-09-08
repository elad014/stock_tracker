import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

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

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(
        self,
        sql: str,
        *params: Any,
        conn: Optional[asyncpg.Connection] = None,
    ) -> str:
        if conn is not None:
            return await conn.execute(sql, *params)
        pool = await self._get_pool()
        return await pool.execute(sql, *params)

    async def fetch_one(
        self,
        sql: str,
        *params: Any,
        conn: Optional[asyncpg.Connection] = None,
    ) -> Optional[dict]:
        if conn is not None:
            row = await conn.fetchrow(sql, *params)
        else:
            pool = await self._get_pool()
            row = await pool.fetchrow(sql, *params)
        return dict(row) if row else None

    async def fetch_all(
        self,
        sql: str,
        *params: Any,
        conn: Optional[asyncpg.Connection] = None,
    ) -> list[dict]:
        if conn is not None:
            rows = await conn.fetch(sql, *params)
        else:
            pool = await self._get_pool()
            rows = await pool.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def executemany(
        self,
        sql: str,
        args: list[tuple[Any, ...]],
        conn: Optional[asyncpg.Connection] = None,
    ) -> None:
        if conn is not None:
            await conn.executemany(sql, args)
            return
        pool = await self._get_pool()
        async with pool.acquire() as acquired:
            await acquired.executemany(sql, args)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None


db = NeonClient()
