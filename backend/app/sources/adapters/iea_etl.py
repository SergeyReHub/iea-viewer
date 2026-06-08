from __future__ import annotations

import re
from collections import Counter
from typing import Any

import asyncpg

from app.metadata.tables import (
    ALLOWED_DOMAINS,
    MAP_TABLES_BY_DOMAIN,
    TABLES_BY_DOMAIN,
    get_table_meta,
    normalize_table_name,
)
from app.sources.adapters.base import CatalogAdapter


def _normalize_period_label(period: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
        return period[:7]
    return period


def _period_rank(period: str) -> tuple[int, int, int, str]:
    year_match = re.fullmatch(r"(\d{4})", period)
    if year_match:
        return (int(year_match.group(1)), 0, 0, period)
    month_match = re.fullmatch(r"(\d{4})-(\d{2})", period)
    if month_match:
        return (int(month_match.group(1)), int(month_match.group(2)), 0, period)
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", period, flags=re.IGNORECASE)
    if quarter_match:
        return (int(quarter_match.group(1)), int(quarter_match.group(2)) * 3, 0, period)
    return (0, 0, 0, period)


class IeaEtlAdapter(CatalogAdapter):
    source_id = "iea"

    async def get_data_as_of_period(self, pool: asyncpg.Pool) -> str | None:
        period_counts: Counter[str] = Counter()

        async with pool.acquire() as conn:
            for domain, tables in TABLES_BY_DOMAIN.items():
                if domain == "base":
                    continue
                for meta in tables:
                    if meta.table_type != "fact":
                        continue
                    schema, table_name = meta.table.split(".", 1)
                    columns = await conn.fetch(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = $1
                          AND table_name = $2
                        """,
                        schema,
                        table_name,
                    )
                    column_names = {str(row["column_name"]) for row in columns}
                    if "time_period" not in column_names:
                        continue

                    if "frequency_code" in column_names:
                        max_period = await conn.fetchval(
                            f"""
                            SELECT MAX(time_period::text)
                            FROM "{schema}"."{table_name}"
                            WHERE frequency_code::text = 'M'
                            """
                        )
                    else:
                        max_period = await conn.fetchval(
                            f"""
                            SELECT MAX(time_period::text)
                            FROM "{schema}"."{table_name}"
                            """
                        )

                    if max_period:
                        period_counts[_normalize_period_label(str(max_period))] += 1

        if not period_counts:
            return None

        return max(
            period_counts.keys(),
            key=lambda period: (period_counts[period], _period_rank(period)),
        )

    async def list_domains(self) -> list[str]:
        return list(ALLOWED_DOMAINS)

    async def list_tables(self, domain: str, table_type: str | None = None) -> list[dict[str, Any]]:
        if domain not in TABLES_BY_DOMAIN:
            return []
        tables = list(TABLES_BY_DOMAIN[domain])
        if domain in MAP_TABLES_BY_DOMAIN:
            tables.extend(MAP_TABLES_BY_DOMAIN[domain])
        if table_type is not None:
            tables = [t for t in tables if t.table_type == table_type]
        return [
            {
                "table": t.table,
                "type": t.table_type,
                "description": t.description,
            }
            for t in tables
        ]

    async def get_table_meta(self, domain: str, table: str) -> dict[str, Any] | None:
        meta = get_table_meta(domain, table)
        if meta is None:
            normalized = normalize_table_name(domain, table)
            for map_table in MAP_TABLES_BY_DOMAIN.get(domain, []):
                if map_table.table == normalized:
                    meta = map_table
                    break
        if meta is None:
            return None
        return {
            "table": meta.table,
            "type": meta.table_type,
            "description": meta.description,
            "doc_file": meta.doc_file,
        }

    async def health_details(self, pool: asyncpg.Pool) -> dict[str, Any]:
        async with pool.acquire() as conn:
            schemas = await conn.fetch(
                """
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name = ANY($1::text[])
                """,
                list(ALLOWED_DOMAINS),
            )
            fact_count = await conn.fetchval(
                """
                SELECT COUNT(*)::int FROM information_schema.tables
                WHERE table_schema = ANY($1::text[])
                  AND table_name LIKE 'fact_%'
                """,
                list(ALLOWED_DOMAINS),
            )
        return {
            "schemas_found": [r["schema_name"] for r in schemas],
            "fact_table_count": fact_count,
            "expected_domains": list(ALLOWED_DOMAINS),
        }


def get_adapter(adapter_name: str) -> CatalogAdapter:
    if adapter_name == "iea_etl":
        return IeaEtlAdapter()
    raise ValueError(f"Unsupported adapter: {adapter_name}")
