from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

import asyncpg

_current_source_id: ContextVar[Optional[str]] = ContextVar("source_id", default=None)
_current_pool: ContextVar[Optional[asyncpg.Pool]] = ContextVar("pool", default=None)


def set_db_context(source_id: str, pool: asyncpg.Pool) -> None:
    _current_source_id.set(source_id)
    _current_pool.set(pool)


def clear_db_context() -> None:
    _current_source_id.set(None)
    _current_pool.set(None)


def get_current_source_id() -> str:
    source_id = _current_source_id.get()
    if not source_id:
        raise RuntimeError("Database source context is not set")
    return source_id


def get_pool() -> asyncpg.Pool:
    pool = _current_pool.get()
    if pool is None:
        raise RuntimeError("Database pool is not initialized in context")
    return pool
