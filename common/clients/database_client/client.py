import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlsplit

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Neon's pooled endpoint is PgBouncer in transaction mode. It only tracks
# client_encoding, datestyle, timezone, standard_conforming_strings and
# application_name, and rejects the connection outright with
# "unsupported startup parameter: search_path" for anything else.
_POOLED_HOST_MARKER = "-pooler."


def _is_pooled_endpoint(database_url: str) -> bool:
    """True when the DSN points at Neon's PgBouncer endpoint."""
    hostname = urlsplit(database_url).hostname or ""
    return _POOLED_HOST_MARKER in hostname


class NeonClient:
    """PostgreSQL client for Neon using asyncpg direct connection."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> None:
        self._database_url: str = database_url or os.getenv("DATABASE_URL", "")
        self._schema: str = schema or os.getenv("DB_SCHEMA", "public")
        self._pool: Optional[asyncpg.Pool] = None

    def _server_settings(self) -> dict[str, str]:
        """search_path for the pool, scoping this service to its own schema."""
        if not self._schema:
            return {}
        if _is_pooled_endpoint(self._database_url):
            # The pooler would refuse the connection. Fall back to the role's
            # server-side default, set by
            # sql/migrations/001_schema_role_isolation.sql via
            # ALTER ROLE ... SET search_path.
            logger.warning(
                "Pooled Neon endpoint in use; DB_SCHEMA=%s is not applied per "
                "connection. The search_path default of the database role "
                "applies instead.",
                self._schema,
            )
            return {}
        return {"search_path": self._schema}

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            # search_path is applied at connection startup, so every connection
            # the pool hands out is already scoped to this service's schema and
            # the unqualified table names in the queries resolve there.
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=10,
                ssl="require",
                server_settings=self._server_settings(),
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
