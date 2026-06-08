"""Server-side SQL aggregation for master report pivot (v2 performance path)."""

from __future__ import annotations

from typing import Any

import asyncpg

from app.db.connection import quote_identifier, split_schema_table


async def fetch_aggregated_report_rows(
    pool: asyncpg.Pool,
    fact_table: str,
    filter_columns: dict[str, list[str]],
    time_column: str = "time_period",
    value_column: str = "value",
    limit: int = 50000,
) -> list[dict[str, Any]]:
    """Aggregate fact rows in SQL before in-memory pivot."""
    schema, table = split_schema_table(fact_table)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    safe_time = quote_identifier(time_column)
    safe_value = quote_identifier(value_column)

    where_parts: list[str] = []
    params: list[Any] = []
    idx = 1
    group_cols = [safe_time]
    select_dims: list[str] = [f"{safe_time}::text AS time_period"]

    for key, values in filter_columns.items():
        if not values:
            continue
        safe_key = quote_identifier(key)
        where_parts.append(f"{safe_key} = ANY(${idx}::text[])")
        params.append(values)
        idx += 1
        group_cols.append(safe_key)
        select_dims.append(f"{safe_key}::text AS {key}")

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    group_sql = ", ".join(group_cols)
    select_sql = ", ".join(select_dims)

    query = f"""
        SELECT
            {select_sql},
            SUM({safe_value}::numeric) AS value,
            COUNT(*)::int AS row_count
        FROM {safe_table}
        {where_sql}
        GROUP BY {group_sql}
        ORDER BY {safe_time}
        LIMIT ${idx}
    """
    params.append(limit)

    async with pool.acquire() as conn:
        records = await conn.fetch(query, *params)
    return [dict(row) for row in records]
