from __future__ import annotations

import os
from typing import Optional

import asyncpg

from app.sources.registry import SourceProfile, SourceRegistry


class ConnectionPoolManager:
    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry
        self._pools: dict[str, asyncpg.Pool] = {}
        self._min_size = int(os.environ.get("DB_POOL_MIN", "1"))
        self._max_size = int(os.environ.get("DB_POOL_MAX", "5"))

    async def init_all(self) -> None:
        for profile in self._registry.list_profiles():
            if profile.status == "active" and profile.connection_url():
                await self._ensure_pool(profile.id)

    async def close_all(self) -> None:
        for pool in self._pools.values():
            await pool.close()
        self._pools.clear()

    async def _ensure_pool(self, source_id: str) -> asyncpg.Pool:
        if source_id in self._pools:
            return self._pools[source_id]
        profile = self._registry.require(source_id)
        url = profile.connection_url()
        if not url:
            raise RuntimeError(f"No connection URL for source {source_id}")
        pool = await asyncpg.create_pool(
            dsn=url,
            min_size=self._min_size,
            max_size=self._max_size,
        )
        self._pools[source_id] = pool
        return pool

    async def get_pool(self, source_id: str) -> asyncpg.Pool:
        profile = self._registry.require(source_id)
        if profile.status != "active":
            raise ValueError(f"Source {source_id} is not active")
        return await self._ensure_pool(source_id)

    async def health_check(self, source_id: str) -> dict[str, object]:
        profile = self._registry.require(source_id)
        if profile.status != "active":
            return {
                "source_id": source_id,
                "status": profile.status,
                "db_ok": False,
                "message": "Source is not active",
            }
        try:
            pool = await self.get_pool(source_id)
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"source_id": source_id, "status": "active", "db_ok": True}
        except Exception as exc:  # noqa: BLE001
            return {
                "source_id": source_id,
                "status": "active",
                "db_ok": False,
                "message": str(exc),
            }


_pool_manager: Optional[ConnectionPoolManager] = None


def get_pool_manager() -> ConnectionPoolManager:
    global _pool_manager
    if _pool_manager is None:
        from app.sources.registry import get_registry

        _pool_manager = ConnectionPoolManager(get_registry())
    return _pool_manager
