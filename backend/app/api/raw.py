import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.db.connection import (
    fetch_distinct_values,
    fetch_grouped_counts,
    fetch_multivalue_fields,
    fetch_rows,
    fetch_table_columns,
    fetch_value_counts,
    get_pool,
    quote_identifier,
    split_schema_table,
)
from app.metadata.tables import TABLES_BY_DOMAIN, normalize_table_name

router = APIRouter(prefix="/raw", tags=["raw"])


RowAxisKey = Literal["country", "flow"]

ROW_AXIS_LABELS: dict[RowAxisKey, str] = {
    "country": "Страны",
    "flow": "Потоки",
}

ROW_AXIS_CANDIDATES: dict[RowAxisKey, list[str]] = {
    "country": ["country_code", "reporter_code", "partner_country_code", "partner_code"],
    "flow": ["flow_code", "ncv_flow_code"],
}
COUNTRY_COLUMN_CANDIDATES = ["country_code", "reporter_code", "partner_country_code", "partner_code"]
FLOW_COLUMN_CANDIDATES = ["flow_code", "ncv_flow_code"]
DETAIL_COLUMN_CANDIDATES_FOR_COUNTRY = [
    *FLOW_COLUMN_CANDIDATES,
    "stock_type",
    "product_code",
    "plant_type_code",
    "indicator_code",
]
DIMENSION_LABELS: dict[str, str] = {
    "country_code": "Страна",
    "reporter_code": "Страна-репортер",
    "partner_country_code": "Страна-партнер",
    "partner_code": "Страна-партнер",
    "flow_code": "Поток",
    "ncv_flow_code": "NCV-поток",
    "product_code": "Продукт",
    "frequency_code": "Частота",
    "unit_code": "Единица",
    "source_id": "Источник",
    "plant_type_code": "Тип станции",
    "indicator_code": "Индикатор",
    "stock_type": "Тип запасов",
    "qualifier": "Квалификатор",
    "conf_status": "Конфиденциальность",
    "data_status": "Статус данных",
}
QUALIFIER_LABELS: dict[str, str] = {
    "A": "Нормальное значение",
    "I": "Оценка IEA",
    "O": "Данные отсутствуют",
    "M": "Неприменимо",
    "P": "Предварительные данные",
    "C": "Конфиденциальные данные",
    "D": "Отличается определение",
    "N": "Квалификация недоступна",
}
CONF_STATUS_LABELS: dict[str, str] = {
    "F": "Неконфиденциальные данные",
    "C": "Конфиденциальные данные",
}
DATA_STATUS_LABELS: dict[str, str] = {
    "A": "Фактические данные",
    "E": "Оценка",
    "P": "Предварительные данные",
    "M": "Модельная оценка",
}
STOCK_TYPE_LABELS: dict[str, str] = {
    "GOVERNMENT": "Государственные запасы",
    "INDUSTRY": "Коммерческие запасы",
    "TOTAL": "Итого",
}
FREQUENCY_LABELS: dict[str, str] = {
    "A": "Ежегодно",
    "Q": "Ежеквартально",
    "M": "Ежемесячно",
    "W": "Еженедельно",
    "D": "Ежедневно",
}


def _period_sort_key(value: str) -> tuple[int, int, int]:
    year_match = re.fullmatch(r"(\d{4})", value)
    if year_match:
        return (int(year_match.group(1)), 0, 0)
    day_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if day_match:
        return (int(day_match.group(1)), int(day_match.group(2)), int(day_match.group(3)))
    month_match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if month_match:
        return (int(month_match.group(1)), int(month_match.group(2)), 0)
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", value, flags=re.IGNORECASE)
    if quarter_match:
        return (int(quarter_match.group(1)), int(quarter_match.group(2)) * 3, 0)
    return (9999, 99, 99)


def _resolve_available_row_axes(columns: set[str]) -> dict[RowAxisKey, str]:
    resolved: dict[RowAxisKey, str] = {}
    for axis_key, candidates in ROW_AXIS_CANDIDATES.items():
        for candidate in candidates:
            if candidate in columns:
                resolved[axis_key] = candidate
                break
    return resolved


def _pick_row_axis(requested: RowAxisKey | None, available_axes: dict[RowAxisKey, str]) -> RowAxisKey:
    if requested is not None and requested in available_axes:
        return requested
    if "country" in available_axes:
        return "country"
    return next(iter(available_axes.keys()))


def _pick_first_existing(columns: set[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


async def _fetch_label_map(
    table_name: str,
    code_column: str,
    name_ru_column: str,
    name_en_column: str,
) -> dict[str, str]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_schema = quote_identifier(schema)
    safe_table = quote_identifier(table)
    safe_code = quote_identifier(code_column)
    safe_name_ru = quote_identifier(name_ru_column)
    safe_name_en = quote_identifier(name_en_column)
    query = f"""
        SELECT
            {safe_code}::text AS code,
            COALESCE(NULLIF({safe_name_ru}, ''), {safe_name_en}, {safe_code}::text) AS label
        FROM {safe_schema}.{safe_table}
        WHERE {safe_code} IS NOT NULL
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return {str(row["code"]): str(row["label"]) for row in rows}


async def _fetch_hierarchy_ordered_items(
    table_name: str,
    code_column: str,
    name_ru_column: str,
    name_en_column: str,
    parent_column: str,
) -> list[dict[str, str]]:
    pool = get_pool()
    schema, table = split_schema_table(table_name)
    safe_schema = quote_identifier(schema)
    safe_table = quote_identifier(table)
    safe_code = quote_identifier(code_column)
    safe_name_ru = quote_identifier(name_ru_column)
    safe_name_en = quote_identifier(name_en_column)
    safe_parent = quote_identifier(parent_column)
    query = f"""
        WITH RECURSIVE hierarchy AS (
            SELECT
                {safe_code}::text AS code,
                COALESCE(NULLIF({safe_name_ru}, ''), {safe_name_en}, {safe_code}::text) AS label,
                {safe_parent}::text AS parent_code,
                0::int AS depth
            FROM {safe_schema}.{safe_table}
            WHERE {safe_parent} IS NULL
            UNION ALL
            SELECT
                child.{safe_code}::text AS code,
                COALESCE(NULLIF(child.{safe_name_ru}, ''), child.{safe_name_en}, child.{safe_code}::text) AS label,
                child.{safe_parent}::text AS parent_code,
                parent.depth + 1 AS depth
            FROM {safe_schema}.{safe_table} child
            JOIN hierarchy parent ON child.{safe_parent}::text = parent.code
        )
        SELECT code, label
        FROM hierarchy
        ORDER BY depth, label
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [{"key": str(row["code"]), "label": str(row["label"])} for row in rows]


async def _resolve_dimension_value_labels(field: str, fact_table: str) -> dict[str, str]:
    if field in {"country_code", "reporter_code", "partner_country_code", "partner_code"}:
        return await _fetch_label_map(
            table_name="base.ref_country",
            code_column="country_code",
            name_ru_column="country_name_ru",
            name_en_column="country_name",
        )
    if field == "flow_code":
        return await _fetch_label_map(
            table_name="base.ref_energy_flow",
            code_column="flow_code",
            name_ru_column="flow_name_ru",
            name_en_column="flow_name",
        )
    if field == "ncv_flow_code":
        return await _fetch_label_map(
            table_name="coal.ref_coal_ncv_flow",
            code_column="ncv_flow_code",
            name_ru_column="ncv_flow_name_ru",
            name_en_column="ncv_flow_name",
        )
    if field == "product_code":
        if fact_table.startswith("oil."):
            return await _fetch_label_map(
                table_name="oil.ref_oil_product",
                code_column="product_code",
                name_ru_column="product_name_ru",
                name_en_column="product_name",
            )
        if fact_table.startswith("gas."):
            return await _fetch_label_map(
                table_name="gas.ref_gas_product",
                code_column="product_code",
                name_ru_column="product_name_ru",
                name_en_column="product_name",
            )
        if fact_table.startswith("electricity."):
            return await _fetch_label_map(
                table_name="electricity.ref_electricity_product",
                code_column="product_code",
                name_ru_column="product_name_ru",
                name_en_column="product_name",
            )
        return await _fetch_label_map(
            table_name="coal.ref_coal_product",
            code_column="product_code",
            name_ru_column="product_name_ru",
            name_en_column="product_name",
        )
    if field == "plant_type_code":
        return await _fetch_label_map(
            table_name="electricity.ref_electricity_plant_type",
            code_column="plant_type_code",
            name_ru_column="plant_type_name_ru",
            name_en_column="plant_type_name",
        )
    if field == "indicator_code":
        return await _fetch_label_map(
            table_name="electricity.ref_electricity_indicator",
            code_column="indicator_code",
            name_ru_column="indicator_name_ru",
            name_en_column="indicator_name",
        )
    if field == "unit_code":
        return await _fetch_label_map(
            table_name="base.ref_unit",
            code_column="unit_code",
            name_ru_column="unit_name_ru",
            name_en_column="unit_name",
        )
    if field == "source_id":
        return await _fetch_label_map(
            table_name="base.ref_data_source",
            code_column="source_id",
            name_ru_column="source_name",
            name_en_column="source_name",
        )
    if field == "frequency_code":
        return FREQUENCY_LABELS
    if field == "qualifier":
        return QUALIFIER_LABELS
    if field == "conf_status":
        return CONF_STATUS_LABELS
    if field == "data_status":
        return DATA_STATUS_LABELS
    if field == "stock_type":
        return STOCK_TYPE_LABELS
    return {}


def _in_period_range(period: str, period_from: str | None, period_to: str | None) -> bool:
    key = _period_sort_key(period)
    if period_from:
        if key < _period_sort_key(period_from):
            return False
    if period_to:
        if key > _period_sort_key(period_to):
            return False
    return True


@router.get("/stats/{domain}/{table_name:path}")
async def get_raw_stats(
    domain: Literal["base", "oil", "gas", "coal", "electricity"],
    table_name: str,
    row_axis: RowAxisKey | None = Query(default=None),
    frequency_code: str | None = Query(default=None),
    period_from: str | None = Query(default=None),
    period_to: str | None = Query(default=None),
) -> dict[str, object]:
    normalized_table_name = normalize_table_name(domain, table_name)

    allowed_fact_tables = {
        table.table
        for table in TABLES_BY_DOMAIN[domain]
        if table.table_type == "fact"
    }
    if normalized_table_name not in allowed_fact_tables:
        raise HTTPException(
            status_code=400,
            detail="Only fact_* tables from selected domain are allowed",
        )

    columns = await fetch_table_columns(normalized_table_name)
    available_row_axes = _resolve_available_row_axes(columns)
    if not available_row_axes:
        raise HTTPException(
            status_code=400,
            detail="No compatible row axes found for this table",
        )
    if "time_period" not in columns:
        raise HTTPException(status_code=400, detail="time_period column is required")

    selected_row_axis = _pick_row_axis(row_axis, available_row_axes)
    row_column = available_row_axes[selected_row_axis]

    frequency_options = (
        sorted(
            await fetch_distinct_values(
                normalized_table_name,
                "frequency_code",
                exclude_zero_value=True,
            )
        )
        if "frequency_code" in columns
        else []
    )
    selected_frequency_code = frequency_code
    if frequency_options:
        if selected_frequency_code not in frequency_options:
            selected_frequency_code = frequency_options[0]
    else:
        selected_frequency_code = None

    equals_filters: dict[str, str] = {}
    if selected_frequency_code is not None:
        equals_filters["frequency_code"] = selected_frequency_code

    raw_cells = await fetch_grouped_counts(
        normalized_table_name,
        row_column=row_column,
        col_column="time_period",
        equals_filters=equals_filters,
        exclude_zero_value=True,
    )
    cells = [
        item
        for item in raw_cells
        if _in_period_range(str(item["col_key"]), period_from, period_to)
    ]
    period_labels_all = sorted(
        await fetch_distinct_values(
            normalized_table_name,
            "time_period",
            equals_filters=equals_filters,
            exclude_zero_value=False,
        ),
        key=_period_sort_key,
    )
    period_labels = [period for period in period_labels_all if _in_period_range(period, period_from, period_to)]

    hierarchy_items: list[dict[str, str]]
    if selected_row_axis == "country":
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="base.ref_country",
            code_column="country_code",
            name_ru_column="country_name_ru",
            name_en_column="country_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="base.ref_country",
            code_column="country_code",
            name_ru_column="country_name_ru",
            name_en_column="country_name",
        )
    elif row_column == "ncv_flow_code":
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="coal.ref_coal_ncv_flow",
            code_column="ncv_flow_code",
            name_ru_column="ncv_flow_name_ru",
            name_en_column="ncv_flow_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="coal.ref_coal_ncv_flow",
            code_column="ncv_flow_code",
            name_ru_column="ncv_flow_name_ru",
            name_en_column="ncv_flow_name",
        )
    else:
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="base.ref_energy_flow",
            code_column="flow_code",
            name_ru_column="flow_name_ru",
            name_en_column="flow_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="base.ref_energy_flow",
            code_column="flow_code",
            name_ru_column="flow_name_ru",
            name_en_column="flow_name",
        )

    fact_row_codes = set(
        await fetch_distinct_values(
            normalized_table_name,
            row_column,
            equals_filters=equals_filters,
            exclude_zero_value=False,
        )
    )
    all_row_codes = (
        fact_row_codes
        if selected_row_axis == "flow"
        else (set(label_map.keys()) | fact_row_codes)
    )
    row_items = [item for item in hierarchy_items if item["key"] in all_row_codes]
    existing_keys = {item["key"] for item in row_items}
    extra_codes = sorted(all_row_codes - existing_keys, key=lambda code: label_map.get(code, code))
    row_items.extend({"key": code, "label": label_map.get(code, code)} for code in extra_codes)

    max_count = max((int(item["count"]) for item in cells), default=0)
    min_count = min((int(item["count"]) for item in cells), default=0)

    return {
        "domain": domain,
        "table": normalized_table_name,
        "row_axis": selected_row_axis,
        "row_axis_label": "Страна" if selected_row_axis == "country" else "Поток",
        "frequency_code": selected_frequency_code,
        "row_column": row_column,
        "col_column": "time_period",
        "available_row_axes": [
            {"key": axis_key, "label": ROW_AXIS_LABELS[axis_key], "column": column}
            for axis_key, column in available_row_axes.items()
        ],
        "available_frequency_codes": frequency_options,
        "period_values": period_labels_all,
        "row_items": row_items,
        "col_labels": period_labels,
        "min_count": min_count,
        "max_count": max_count,
        "cells": [
            {
                "row_key": str(item["row_key"]),
                "col_key": str(item["col_key"]),
                "count": int(item["count"]),
            }
            for item in cells
        ],
    }


@router.get("/stats-detail/{domain}/{table_name:path}")
async def get_raw_stats_detail(
    domain: Literal["base", "oil", "gas", "coal", "electricity"],
    table_name: str,
    row_axis: RowAxisKey = Query(...),
    row_key: str = Query(...),
    time_period: str = Query(...),
    frequency_code: str | None = Query(default=None),
) -> dict[str, object]:
    normalized_table_name = normalize_table_name(domain, table_name)
    allowed_fact_tables = {
        table.table
        for table in TABLES_BY_DOMAIN[domain]
        if table.table_type == "fact"
    }
    if normalized_table_name not in allowed_fact_tables:
        raise HTTPException(
            status_code=400,
            detail="Only fact_* tables from selected domain are allowed",
        )

    columns = await fetch_table_columns(normalized_table_name)
    available_row_axes = _resolve_available_row_axes(columns)
    if row_axis not in available_row_axes:
        raise HTTPException(status_code=400, detail="Unsupported row axis for this table")

    row_column = available_row_axes[row_axis]
    detail_column = (
        _pick_first_existing(columns, DETAIL_COLUMN_CANDIDATES_FOR_COUNTRY)
        if row_axis == "country"
        else _pick_first_existing(columns, COUNTRY_COLUMN_CANDIDATES)
    )
    if detail_column is None:
        raise HTTPException(status_code=400, detail="No compatible detail axis found for this table")

    equals_filters: dict[str, str] = {
        row_column: row_key,
        "time_period": time_period,
    }
    if frequency_code:
        equals_filters["frequency_code"] = frequency_code

    counts = await fetch_value_counts(
        normalized_table_name,
        column=detail_column,
        equals_filters=equals_filters,
        exclude_zero_value=True,
    )
    count_map = {item["key"]: item["count"] for item in counts}

    if detail_column in COUNTRY_COLUMN_CANDIDATES:
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="base.ref_country",
            code_column="country_code",
            name_ru_column="country_name_ru",
            name_en_column="country_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="base.ref_country",
            code_column="country_code",
            name_ru_column="country_name_ru",
            name_en_column="country_name",
        )
        detail_axis_label = "Страны"
    elif detail_column == "ncv_flow_code":
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="coal.ref_coal_ncv_flow",
            code_column="ncv_flow_code",
            name_ru_column="ncv_flow_name_ru",
            name_en_column="ncv_flow_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="coal.ref_coal_ncv_flow",
            code_column="ncv_flow_code",
            name_ru_column="ncv_flow_name_ru",
            name_en_column="ncv_flow_name",
        )
        detail_axis_label = "Потоки"
    elif detail_column == "stock_type":
        label_map = STOCK_TYPE_LABELS
        hierarchy_items = [{"key": key, "label": value} for key, value in STOCK_TYPE_LABELS.items()]
        detail_axis_label = "Тип запасов"
    elif detail_column == "product_code":
        if normalized_table_name.startswith("oil."):
            product_table = "oil.ref_oil_product"
        elif normalized_table_name.startswith("gas."):
            product_table = "gas.ref_gas_product"
        elif normalized_table_name.startswith("electricity."):
            product_table = "electricity.ref_electricity_product"
        else:
            product_table = "coal.ref_coal_product"
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name=product_table,
            code_column="product_code",
            name_ru_column="product_name_ru",
            name_en_column="product_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name=product_table,
            code_column="product_code",
            name_ru_column="product_name_ru",
            name_en_column="product_name",
        )
        detail_axis_label = "Продукты"
    elif detail_column == "plant_type_code":
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="electricity.ref_electricity_plant_type",
            code_column="plant_type_code",
            name_ru_column="plant_type_name_ru",
            name_en_column="plant_type_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="electricity.ref_electricity_plant_type",
            code_column="plant_type_code",
            name_ru_column="plant_type_name_ru",
            name_en_column="plant_type_name",
        )
        detail_axis_label = "Типы станций"
    elif detail_column == "indicator_code":
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="electricity.ref_electricity_indicator",
            code_column="indicator_code",
            name_ru_column="indicator_name_ru",
            name_en_column="indicator_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="electricity.ref_electricity_indicator",
            code_column="indicator_code",
            name_ru_column="indicator_name_ru",
            name_en_column="indicator_name",
        )
        detail_axis_label = "Индикаторы"
    else:
        hierarchy_items = await _fetch_hierarchy_ordered_items(
            table_name="base.ref_energy_flow",
            code_column="flow_code",
            name_ru_column="flow_name_ru",
            name_en_column="flow_name",
            parent_column="parent_code",
        )
        label_map = await _fetch_label_map(
            table_name="base.ref_energy_flow",
            code_column="flow_code",
            name_ru_column="flow_name_ru",
            name_en_column="flow_name",
        )
        detail_axis_label = "Потоки"

    present_keys = set(count_map.keys())
    ordered_items = [item for item in hierarchy_items if item["key"] in present_keys]
    ordered_keys = {item["key"] for item in ordered_items}
    extra_keys = sorted(present_keys - ordered_keys, key=lambda key: label_map.get(key, key))
    ordered_items.extend({"key": key, "label": label_map.get(key, key)} for key in extra_keys)

    skip_columns = {
        "id",
        "load_batch_id",
        "created_at",
        "updated_at",
        "time_period_start",
        "value",
        "time_period",
        row_column,
        detail_column,
    }
    if frequency_code:
        skip_columns.add("frequency_code")
    candidate_columns = sorted(column for column in columns if column not in skip_columns)
    ambiguity_dimensions_raw = await fetch_multivalue_fields(
        table_name=normalized_table_name,
        columns=candidate_columns,
        equals_filters=equals_filters,
        exclude_zero_value=True,
        max_values_per_field=30,
    )
    value_label_maps: dict[str, dict[str, str]] = {}
    ambiguity_dimensions = []
    for item in ambiguity_dimensions_raw:
        field = item["field"]
        if field not in value_label_maps:
            value_label_maps[field] = await _resolve_dimension_value_labels(field, normalized_table_name)
        value_labels = value_label_maps[field]
        mapped_values: list[str] = []
        seen_values: set[str] = set()
        for raw_value in item["values"]:
            mapped = value_labels.get(raw_value, raw_value)
            if mapped in seen_values:
                continue
            seen_values.add(mapped)
            mapped_values.append(mapped)
        ambiguity_dimensions.append(
            {
                "field": field,
                "label": DIMENSION_LABELS.get(field, field),
                "count": item["count"],
                "values": mapped_values,
                "truncated": item["truncated"],
            }
        )

    return {
        "domain": domain,
        "table": normalized_table_name,
        "row_axis": row_axis,
        "row_key": row_key,
        "time_period": time_period,
        "frequency_code": frequency_code,
        "detail_axis_label": detail_axis_label,
        "items": [
            {
                "key": item["key"],
                "label": item["label"],
                "count": count_map.get(item["key"], 0),
            }
            for item in ordered_items
        ],
        "ambiguity_dimensions": ambiguity_dimensions,
    }


@router.get("/{domain}/{table_name:path}")
async def get_raw_rows(
    domain: Literal["base", "oil", "gas", "coal", "electricity"],
    table_name: str,
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, object]:
    normalized_table_name = normalize_table_name(domain, table_name)

    allowed_fact_tables = {
        table.table
        for table in TABLES_BY_DOMAIN[domain]
        if table.table_type == "fact"
    }
    if normalized_table_name not in allowed_fact_tables:
        raise HTTPException(
            status_code=400,
            detail="Only fact_* tables from selected domain are allowed",
        )

    rows = await fetch_rows(normalized_table_name, limit)
    columns = list(rows[0].keys()) if rows else []
    return {
        "domain": domain,
        "table": normalized_table_name,
        "limit": limit,
        "count": len(rows),
        "columns": columns,
        "rows": rows,
    }
