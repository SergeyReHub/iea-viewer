from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import asyncpg


class CatalogAdapter(ABC):
    source_id: str

    @abstractmethod
    async def list_domains(self) -> list[str]:
        ...

    @abstractmethod
    async def list_tables(self, domain: str, table_type: str | None = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_table_meta(self, domain: str, table: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def health_details(self, pool: asyncpg.Pool) -> dict[str, Any]:
        ...
