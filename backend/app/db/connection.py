from typing import Any, Iterable, Optional

import asyncpg

from app.db.context import get_pool


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def split_schema_table(table_name: str) -> tuple[str, str]:
    if "." in table_name:
        schema, table = table_name.split(".", 1)
        return schema, table
    return "public", table_name


async def fetch_rows(table_name: str, limit: int) -> list[dict[str, Any]]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    query = f"SELECT * FROM {safe_table} LIMIT $1"
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query, limit)
    return [dict(record) for record in records]


async def fetch_all_rows(table_name: str) -> list[dict[str, Any]]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    query = f"SELECT * FROM {safe_table}"
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query)
    return [dict(record) for record in records]


async def fetch_table_columns(table_name: str) -> set[str]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query, schema, table)
    return {str(record["column_name"]) for record in records}


async def fetch_grouped_counts(
    table_name: str,
    row_column: str,
    col_column: str,
    equals_filters: dict[str, str] | None = None,
    exclude_zero_value: bool = False,
) -> list[dict[str, Any]]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    safe_row_col = quote_identifier(row_column)
    safe_col_col = quote_identifier(col_column)
    where_clauses: list[str] = []
    params: list[Any] = []
    param_idx = 1
    for key, value in (equals_filters or {}).items():
        safe_key = quote_identifier(key)
        where_clauses.append(f"{safe_key}::text = ${param_idx}")
        params.append(value)
        param_idx += 1
    if exclude_zero_value:
        where_clauses.append('COALESCE("value"::numeric, 0) <> 0')
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = f"""
        SELECT
            COALESCE({safe_row_col}::text, '—') AS row_key,
            COALESCE({safe_col_col}::text, '—') AS col_key,
            COUNT(*)::int AS count
        FROM {safe_table}
        {where_sql}
        GROUP BY 1, 2
    """
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query, *params)
    return [dict(record) for record in records]


async def fetch_distinct_values(
    table_name: str,
    column: str,
    equals_filters: dict[str, str] | None = None,
    exclude_zero_value: bool = False,
) -> list[str]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    safe_column = quote_identifier(column)
    where_clauses = [f"{safe_column} IS NOT NULL"]
    params: list[Any] = []
    param_idx = 1
    for key, value in (equals_filters or {}).items():
        safe_key = quote_identifier(key)
        where_clauses.append(f"{safe_key}::text = ${param_idx}")
        params.append(value)
        param_idx += 1
    if exclude_zero_value:
        where_clauses.append('COALESCE("value"::numeric, 0) <> 0')
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    query = f"""
        SELECT DISTINCT {safe_column}::text AS value
        FROM {safe_table}
        {where_sql}
    """
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query, *params)
    return [str(record["value"]) for record in records]


async def fetch_value_counts(
    table_name: str,
    column: str,
    equals_filters: dict[str, str] | None = None,
    exclude_zero_value: bool = False,
) -> list[dict[str, Any]]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    safe_column = quote_identifier(column)
    where_clauses = [f"{safe_column} IS NOT NULL"]
    params: list[Any] = []
    param_idx = 1
    for key, value in (equals_filters or {}).items():
        safe_key = quote_identifier(key)
        where_clauses.append(f"{safe_key}::text = ${param_idx}")
        params.append(value)
        param_idx += 1
    if exclude_zero_value:
        where_clauses.append('COALESCE("value"::numeric, 0) <> 0')
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    query = f"""
        SELECT {safe_column}::text AS key, COUNT(*)::int AS count
        FROM {safe_table}
        {where_sql}
        GROUP BY 1
        ORDER BY 2 DESC, 1
    """
    async with pool.acquire() as conn:
        records: Iterable[asyncpg.Record] = await conn.fetch(query, *params)
    return [{"key": str(record["key"]), "count": int(record["count"])} for record in records]


async def fetch_multivalue_fields(
    table_name: str,
    columns: list[str],
    equals_filters: dict[str, str] | None = None,
    exclude_zero_value: bool = False,
    max_values_per_field: int = 50,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for column in columns:
        values = await fetch_distinct_values(
            table_name=table_name,
            column=column,
            equals_filters=equals_filters,
            exclude_zero_value=exclude_zero_value,
        )
        if len(values) <= 1:
            continue
        result.append(
            {
                "field": column,
                "count": len(values),
                "values": values[:max_values_per_field],
                "truncated": len(values) > max_values_per_field,
            }
        )
    return result


async def fetch_query_rows(query: str, *params: Any) -> list[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(query, *params)
    return [dict(record) for record in records]
