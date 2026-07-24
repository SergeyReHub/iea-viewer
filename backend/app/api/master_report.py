import calendar
from collections import defaultdict
from datetime import datetime
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.connection import get_pool
from app.metadata.tables import TABLES_BY_DOMAIN

router = APIRouter(prefix="/master-report", tags=["master-report"])


class MasterReportFilters(BaseModel):
    fact_table: str = "oil.fact_oil_balance"
    filter_values: dict[str, list[str]] = Field(default_factory=dict)
    limit: int = Field(default=2000, ge=1, le=10000)
    pivot_layout: str = "time_rows_filters_columns"


class FilterOptionsRequest(BaseModel):
    fact_table: str
    selected_filter_values: dict[str, list[str]] = Field(default_factory=dict)


class GuideTableRequest(BaseModel):
    table_id: str
    country_code: str


FACT_TABLE_LABELS = {
    "oil.fact_oil_crude_supply": "Предложение сырой нефти",
    "oil.fact_oil_balance": "Баланс нефтепродуктов",
    "oil.fact_oil_trade": "Торговля нефтью по партнерам",
    "oil.fact_oil_world_supply": "Мировое предложение нефти",
    "oil.fact_oil_conversion": "Коэффициенты пересчета (барр/тонна)",
    "oil.fact_oil_stocks": "Запасы нефти и нефтепродуктов",
    "oil.fact_oil_field_production": "Добыча по месторождениям",
    "oil.fact_oil_refinery_throughput": "Переработка НПЗ",
    "gas.fact_gas_balance": "Баланс природного газа",
    "gas.fact_gas_trade": "Торговля газом по партнерам",
    "coal.fact_coal_balance": "Баланс угля",
    "coal.fact_coal_ncv": "NCV угля",
    "coal.fact_coal_quarterly": "Квартальная статистика угля",
    "coal.fact_coal_trade": "Торговля углем по партнерам",
    "electricity.fact_electricity_balance": "Баланс электроэнергии и тепла",
    "electricity.fact_electricity_trade": "Импорт/экспорт электроэнергии по партнерам",
    "electricity.fact_electricity_generation": "Генерация электроэнергии",
    "electricity.fact_electricity_auto": "Автогенерация электроэнергии",
    "electricity.fact_electricity_capacity": "Установленная мощность электростанций",
}

FILTER_LABELS = {
    "country_code": "Страна",
    "reporter_code": "Страна-отчетчик",
    "partner_code": "Страна-партнер",
    "partner_country_code": "Страна-партнер",
    "product_code": "Продукт",
    "flow_code": "Поток",
    "ncv_flow_code": "NCV-поток",
    "frequency_code": "Период",
    "unit_code": "Единица",
    "source_id": "Источник",
    "field_code": "Месторождение",
    "plant_type_code": "Тип станции",
    "indicator_code": "Индикатор",
    "environment": "Среда",
    "stock_type": "Тип запасов",
    "qualifier": "Квалификатор",
    "conf_status": "Конфиденциальность",
    "data_status": "Статус данных",
    "year": "Год",
    "quarter": "Квартал",
    "time_period": "Период",
    "value": "Значение",
}

QUALIFIER_LABELS = {
    "A": "Нормальное значение",
    "I": "Оценка IEA (расчетное значение)",
    "O": "Данные отсутствуют",
    "M": "Неприменимо",
    "P": "Предварительные данные",
    "C": "Конфиденциальные данные",
    "D": "Отличается определение",
    "N": "Квалификация недоступна",
}

CONF_STATUS_LABELS = {
    "F": "Неконфиденциальные данные",
    "C": "Конфиденциальные данные",
}

# Legacy codes from mea_data / v1 templates → iea_data ETL v2
LEGACY_OIL_PRODUCT_CODES: dict[str, str] = {
    "ADDITIVE": "ADDITIVES",
    "AVGAS": "AVIATION_GASOLINE",
    "BIODIESEL": "BIODIESEL_BLEND",
    "BIOFUELS": "LIQBIOFUEL_BLEND",
    "BIOGASOL": "BIOGASOLINE_BLEND",
    "BIOJET_KER": "KEROSENE_JET_BIO",
    "CRNGFEED": "OIL_PRIM_PRODUCTS",
    "CRUDEOIL": "CRUDE_OIL",
    "DIESEL": "DIESEL_ROAD",
    "FUELOIL_HS": "FUEL_OIL_HIGH_SULPHUR",
    "GASDIES": "GAS_DIESEL_HEAVY_OIL",
    "JETANDKERO": "KEROSENE",
    "JETGAS": "GASOLINE_JET",
    "JETKERO": "KEROSENE_JET",
    "LOWSULF": "FUEL_OIL_LOW_SULPHUR",
    "LPGETHANE": "LPG_ETHANE",
    "LUBRIC": "LUBRICANTS",
    "MIDDIST": "MIDDLE_DISTILLATES",
    "MOTORGAS": "MOTOR_GASOLINE",
    "NONBIODIES": "GAS_DIESEL_OIL_NONBIO",
    "NONBIOGASO": "MOTOR_GASOLINE_NONBIO",
    "NONBIOJETK": "KEROSENE_JET_NONBIO",
    "NONCONV_OILS": "NONCONVENTIONAL_OILS",
    "NONCRUDE": "HYDROCARBONS_OTHER",
    "OIL_PRIM_X_BIO": "OIL_PRIM_PRODS_X_BIOFUELS",
    "OIL_PRIM_X_CRUDE": "OIL_PRIM_PRODS_X_CRUDE",
    "OPRODS": "OTH_SEC_OIL_PRODS_ND",
    "OTHGASOIL": "HEATING_OTHER_GASOIL",
    "OTHKERO": "KEROSENE_OTHER",
    "PARWAX": "PARAFFIN_WAXES",
    "PETCOKE": "PETROLEUM_COKE",
    "REFFEEDS": "REFINERY_FEEDSTOCKS",
    "REFINGAS": "REFINERY_GAS",
    "RESFUEL": "FUEL_OIL_RESIDUAL",
    "TOTALOIL": "OIL_TOTAL",
    "TOTPRODS": "OIL_SEC_PRODUCTS",
    "WHITESP": "WHITE_SPIRIT",
}

LEGACY_SOURCE_IDS: dict[str, str] = {
    "245": "47",
    "43": "57",
}

LEGACY_FLOW_CODES: dict[str, str] = {
    "IMPORT": "IMPORTS",
    "FINCONS": "GRDEL_INLAND_OBS",
    "REFINOBST": "REFININT_OBS",
    "TOTCONS": "GRDEL_INLAND_OBS",
}

OECD_ROOT_CODES = {"TOTOECD", "OECDTOT"}


def _resolve_product_codes(codes: list[str]) -> list[str]:
    resolved: list[str] = []
    for code in codes:
        mapped = LEGACY_OIL_PRODUCT_CODES.get(code, code)
        if mapped not in resolved:
            resolved.append(mapped)
    return resolved


def _normalize_guide_filters(filters: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, values in filters.items():
        if key == "product_code":
            normalized[key] = _resolve_product_codes(values)
        elif key == "source_id":
            normalized[key] = [
                LEGACY_SOURCE_IDS.get(value, value) for value in values
            ]
        elif key == "flow_code":
            normalized[key] = [
                LEGACY_FLOW_CODES.get(value, value) for value in values
            ]
        else:
            normalized[key] = list(values)
    return normalized


def _parse_month_period(value: str) -> tuple[int, int] | None:
    day_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if day_match:
        return int(day_match.group(1)), int(day_match.group(2))
    month_match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if month_match:
        return int(month_match.group(1)), int(month_match.group(2))
    return None


def _month_in_year(period: str, year: int) -> int | None:
    parsed = _parse_month_period(period)
    if parsed and parsed[0] == year:
        return parsed[1]
    return None


def _lookup_period_value(period_values: dict[str, float], period_key: str) -> float | None:
    direct = period_values.get(period_key)
    if direct is not None:
        return direct
    parsed = _parse_month_period(period_key)
    if parsed is None:
        return None
    year, month = parsed
    for key, value in period_values.items():
        key_parsed = _parse_month_period(key)
        if key_parsed == (year, month):
            return value
    return None


def _sum_monthly_values_for_year(
    monthly_values: dict[str, float],
    year: int,
    *,
    require_full_year: bool = True,
) -> float | None:
    values: list[float] = []
    months: set[int] = set()
    for period_key, value in monthly_values.items():
        parsed = _parse_month_period(period_key)
        if parsed is None or parsed[0] != year:
            continue
        months.add(parsed[1])
        values.append(value)
    if not values:
        return None
    if require_full_year and len(months) != 12:
        return None
    return float(sum(values))


def _sum_monthly_values_for_year_months(
    monthly_values: dict[str, float],
    year: int,
    months: range | list[int],
) -> float | None:
    values: list[float] = []
    month_set = set(months)
    for period_key, value in monthly_values.items():
        parsed = _parse_month_period(period_key)
        if parsed is None or parsed[0] != year or parsed[1] not in month_set:
            continue
        values.append(value)
    if not values:
        return None
    return float(sum(values))

GUIDE_TABLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "oil-oecd-crude-production-tonnes": {
        "domain": "oil",
        "title": "Добыча нефти в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_crude_supply",
        "mode": "tz_oecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_labels": {
            "crude": "Сырая нефть",
        },
        "row_products": {
            "crude": ["CRUDEOIL"],
        },
        "sources": [
            {
                "frequency_code": "A",
                "base_filters": {
                    "flow_code": ["INDPROD"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["INDPROD_OSOURCES"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                    "source_id": ["245"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "oil-nonoecd-crude-production-tonnes": {
        "domain": "oil",
        "title": "Добыча нефтяного сырья в стране не-ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_world_supply",
        "mode": "tz_nonoecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_label": "Сырая нефть",
        "row_products": {
            "crude": ["CRNGFEED"],
        },
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2020-01",
                "base_filters": {
                    "flow_code": ["INDPROD_OSOURCES"],
                    "product_code": ["CRNGFEED"],
                    "unit_code": ["KBD"],
                },
            },
        ],
        "fixed_bbl_t": 7.33,
        "country_scope": "non_oecd",
    },
    "oil-oecd-crude-field-production": {
        "domain": "oil",
        "title": "Добыча нефти по месторождениям, (тыс. тонн)",
        "fact_table": "oil.fact_oil_field_production",
        "mode": "tz_oecd_field_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_dimension": "field_code",
        "sources": [
            {
                "frequency_code": "A",
                "base_filters": {
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KBD"],
                    "source_id": ["57"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KBD"],
                    "source_id": ["57"],
                },
            },
        ],
        "fixed_bbl_t": 7.33,
    },
    "oil-oecd-crude-import": {
        "domain": "oil",
        "title": "Импорт нефти в страну ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_crude_supply",
        "mode": "tz_oecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_labels": {
            "crude": "Сырая нефть",
        },
        "row_products": {
            "crude": ["CRUDEOIL"],
        },
        "sources": [
            {
                "frequency_code": "A",
                "base_filters": {
                    "flow_code": ["IMPORTS"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["IMPORTS"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "oil-oecd-crude-export": {
        "domain": "oil",
        "title": "Экспорт нефти из страны ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_crude_supply",
        "mode": "tz_oecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_labels": {
            "crude": "Сырая нефть",
        },
        "row_products": {
            "crude": ["CRUDEOIL"],
        },
        "sources": [
            {
                "frequency_code": "A",
                "base_filters": {
                    "flow_code": ["EXPORTS"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["EXPORTS"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "oil-oecd-oil-import-by-partners": {
        "domain": "oil",
        "title": "Импорт нефти в страну ОЭСР по направлениям, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "flow_code": ["IMPORTS"],
            "product_code": ["CRUDEOIL"],
            "unit_code": ["KT"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "country_scope": "oecd",
    },
    "oil-oecd-oil-export-by-partners": {
        "domain": "oil",
        "title": "Экспорт нефти из страны ОЭСР по направлениям, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": ["partner_country_code", "partner_code"],
        "base_filters": {
            "flow_code": ["EXPORTS"],
            "product_code": ["CRUDEOIL"],
            "unit_code": ["KT"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "country_scope": "oecd",
    },
    "oil-oecd-refinery-throughput": {
        "domain": "oil",
        "title": "Объём первичной переработки нефти в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_crude_supply",
        "mode": "tz_oecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_labels": {
            "crude": "Сырая нефть",
        },
        "row_products": {
            "crude": ["CRUDEOIL"],
        },
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2020-01",
                "base_filters": {
                    "flow_code": ["REFINOBST"],
                    "product_code": ["CRUDEOIL"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "oil-oecd-products-production": {
        "domain": "oil",
        "title": "Производство нефтепродуктов в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_balance",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2020",
                "base_filters": {
                    "flow_code": ["REFINOUT"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["REFINOUT"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-oecd-products-production-structure": {
        "domain": "oil",
        "title": "Структура производства нефтепродуктов в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_balance",
        "mode": "tz_oecd_products_structure",
        "round_digits": 1,
        "other_label": "Прочие нефтепродукты",
        "total_label": "Всего",
        "total_products": ["TOTPRODS"],
        "column_definitions": [
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Керосин", "products": ["JETKERO", "OTHKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["REFINOUT"],
                    "product_code": [
                        "TOTPRODS",
                        "LPG",
                        "MOTORGAS",
                        "JETKERO",
                        "OTHKERO",
                        "GASDIES",
                        "RESFUEL",
                    ],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-oecd-products-consumption": {
        "domain": "oil",
        "title": "Потребление нефтепродуктов в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_balance",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2020",
                "base_filters": {
                    "flow_code": ["FINCONS"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["FINCONS"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-oecd-products-consumption-by-sector": {
        "domain": "oil",
        "title": "Структура потребления нефтепродуктов в стране ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_balance",
        "mode": "tz_oecd_products_structure",
        "round_digits": 1,
        "other_label": "Прочие нефтепродукты",
        "total_label": "Всего",
        "total_products": ["TOTPRODS"],
        "column_definitions": [
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Керосин", "products": ["JETKERO", "OTHKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["FINCONS"],
                    "product_code": [
                        "TOTPRODS",
                        "LPG",
                        "MOTORGAS",
                        "JETKERO",
                        "OTHKERO",
                        "GASDIES",
                        "RESFUEL",
                    ],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-oecd-products-export": {
        "domain": "oil",
        "title": "Экспорт нефтепродуктов из страны ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2020",
                "base_filters": {
                    "flow_code": ["EXPORTS"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["EXPORTS"],
                    "unit_code": ["KT"],
                    "partner_code": ["TOTAL"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-nonoecd-products-export": {
        "domain": "oil",
        "title": "Экспорт нефтепродуктов из страны не-ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": "product_code",
        "base_filters": {"flow_code": ["EXPORTS"]},
        "mode": "annual_series",
        "period_from": "2017",
        "country_scope": "non_oecd",
    },
    "oil-oecd-products-import": {
        "domain": "oil",
        "title": "Импорт нефтепродуктов в страну ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2020",
                "base_filters": {
                    "flow_code": ["IMPORTS"],
                    "unit_code": ["KT"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["IMPORTS"],
                    "unit_code": ["KT"],
                    "partner_code": ["TOTAL"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "oecd",
    },
    "oil-nonoecd-products-import": {
        "domain": "oil",
        "title": "Импорт нефтепродуктов в страну не-ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": "product_code",
        "base_filters": {"flow_code": ["IMPORTS"]},
        "mode": "annual_series",
        "period_from": "2017",
        "country_scope": "non_oecd",
    },
    "oil-nonoecd-products-consumption": {
        "domain": "oil",
        "title": "Потребление нефтепродуктов в стране не-ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_world_supply",
        "mode": "tz_nonoecd_world_supply_annual",
        "period_from": "2019",
        "require_no_oecd_balance": True,
        "qualifier_priority": ["A", "P", "N", "I"],
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2019",
                "base_filters": {
                    "flow_code": ["NETDELIV"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "non_oecd",
    },
    "oil-nonoecd-products-production": {
        "domain": "oil",
        "title": "Производство нефтепродуктов в стране не-ОЭСР, (тыс. тонн)",
        "fact_table": "oil.fact_oil_world_supply",
        "mode": "tz_nonoecd_world_supply_annual",
        "period_from": "2019",
        "require_no_oecd_balance": True,
        "qualifier_priority": ["N", "I"],
        "row_definitions": [
            {"label": "Всего, в т.ч.:", "products": ["TOTPRODS"]},
            {"label": "СУГ", "products": ["LPG"]},
            {"label": "Автобензин", "products": ["MOTORGAS"]},
            {"label": "Авиакеросин", "products": ["JETKERO"]},
            {"label": "Дизтопливо", "products": ["GASDIES"]},
            {"label": "Мазут", "products": ["RESFUEL"]},
        ],
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2019",
                "base_filters": {
                    "flow_code": ["REFINOUT"],
                    "unit_code": ["KT"],
                },
            },
        ],
        "prefer_qualifier": True,
        "country_scope": "non_oecd",
    },
    "oil-oecd-products-import-by-partners": {
        "domain": "oil",
        "title": "Импорт нефтепродуктов в страну ОЭСР по направлениям, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "flow_code": ["IMPORTS"],
            "unit_code": ["KT"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "annual_share_total_product": "TOTPRODS",
        "country_scope": "oecd",
    },
    "oil-oecd-products-export-by-partners": {
        "domain": "oil",
        "title": "Экспорт нефтепродуктов из страны ОЭСР по направлениям, (тыс. тонн)",
        "fact_table": "oil.fact_oil_trade",
        "frequency_code": "A",
        "row_dimension": ["partner_country_code", "partner_code"],
        "base_filters": {
            "flow_code": ["EXPORTS"],
            "unit_code": ["KT"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "annual_share_total_product": "TOTPRODS",
        "country_scope": "oecd",
    },
    "gas-oecd-production": {
        "domain": "gas",
        "title": "Добыча газа в стране ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "mode": "tz_oecd_crude_production",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "value_scale": 0.001,
        "aggregate_period_values": True,
        "row_labels": {
            "crude": "Добыча газа",
        },
        "sources": [
            {
                "frequency_code": "A",
                "period_from": "2020",
                "base_filters": {
                    "flow_code": ["INDPROD"],
                    "unit_code": ["M_M3"],
                },
            },
            {
                "frequency_code": "M",
                "period_from": "2025-01",
                "base_filters": {
                    "flow_code": ["INDPROD"],
                    "unit_code": ["M_M3"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "gas-nonoecd-production": {
        "domain": "gas",
        "title": "Добыча газа в стране не-ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "A",
        "row_dimension": None,
        "base_filters": {
            "flow_code": ["INDPROD"],
            "unit_code": ["M_M3"],
        },
        "mode": "annual_series",
        "period_from": "2020",
        "value_scale": 0.001,
        "round_digits": 1,
        "country_scope": "non_oecd",
    },
    "gas-oecd-import": {
        "domain": "gas",
        "title": "Импорт газа в страну ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "value_scale": 0.001,
        "round_digits": 1,
        "optional_row_labels": ["СПГ"],
        "row_definitions": [
            {"label": "Всего", "products": ["NATURAL_GAS"]},
            {"label": "СПГ", "products": ["LNG"]},
        ],
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2020-01",
                "base_filters": {
                    "flow_code": ["IMPORTS"],
                    "unit_code": ["M_M3"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "gas-oecd-export": {
        "domain": "gas",
        "title": "Экспорт газа из страны ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "mode": "tz_oecd_products_consumption",
        "period_from": "2020",
        "latest_period_label": "{x} мес. {year}",
        "pct_label": "% к {x} мес. {prev_year}",
        "value_scale": 0.001,
        "round_digits": 1,
        "optional_row_labels": ["СПГ"],
        "row_definitions": [
            {"label": "Всего", "products": ["NATURAL_GAS"]},
            {"label": "СПГ", "products": ["LNG"]},
        ],
        "sources": [
            {
                "frequency_code": "M",
                "period_from": "2020-01",
                "base_filters": {
                    "flow_code": ["EXPORTS"],
                    "unit_code": ["M_M3"],
                },
            },
        ],
        "country_scope": "oecd",
    },
    "gas-oecd-export-import": {
        "domain": "gas",
        "title": "Экспорт и импорт газа в стране ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "M",
        "row_dimension": "flow_code",
        "base_filters": {"flow_code": ["IMPORTS", "EXPORTS"]},
        "mode": "monthly_with_yoy",
        "period_from": "2020",
        "latest_period_label": "мес.-5 {year}",
        "pct_label": "% к мес.-5 {prev_year}",
        "country_scope": "oecd",
    },
    "gas-oecd-export-import-annual": {
        "domain": "gas",
        "title": "Экспорт и импорт газа в страну ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "A",
        "row_dimension": "flow_code",
        "base_filters": {"flow_code": ["IMPORTS", "EXPORTS"]},
        "mode": "annual_series",
        "period_from": "2017",
        "country_scope": "oecd",
    },
    "gas-nonoecd-import": {
        "domain": "gas",
        "title": "Импорт газа в страну не-ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "A",
        "row_dimension": None,
        "base_filters": {
            "flow_code": ["IMPORTS"],
            "product_code": ["NATURAL_GAS"],
            "unit_code": ["M_M3"],
        },
        "mode": "annual_series",
        "period_from": "2020",
        "value_scale": 0.001,
        "round_digits": 1,
        "country_scope": "non_oecd",
    },
    "gas-nonoecd-export": {
        "domain": "gas",
        "title": "Экспорт газа из страны не-ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "A",
        "row_dimension": None,
        "base_filters": {
            "flow_code": ["EXPORTS"],
            "product_code": ["NATURAL_GAS"],
            "unit_code": ["M_M3"],
        },
        "mode": "annual_series",
        "period_from": "2020",
        "value_scale": 0.001,
        "round_digits": 1,
        "country_scope": "non_oecd",
    },
    "gas-import-by-partners": {
        "domain": "gas",
        "title": "Импорт газа в страну ОЭСР по направлениям, (млрд м³)",
        "fact_table": "gas.fact_gas_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "flow_code": ["IMPORTS"],
            "product_code": ["NATURAL_GAS"],
            "unit_code": ["M_M3"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "value_scale": 0.001,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "annual_share_total_product": "NATURAL_GAS",
        "country_scope": "oecd",
    },
    "gas-lng-import-by-partners": {
        "domain": "gas",
        "title": "Импорт СПГ в страну по направлениям, (млрд м³)",
        "fact_table": "gas.fact_gas_trade",
        "frequency_code": "A",
        "row_dimension": ["partner_country_code", "partner_code"],
        "base_filters": {"flow_code": ["IMPORTS"]},
        "mode": "annual_share",
        "top_n_rows": 10,
        "country_scope": "oecd",
    },
    "gas-export-by-partners": {
        "domain": "gas",
        "title": "Экспорт газа из страны ОЭСР по направлениям, (млрд м³)",
        "fact_table": "gas.fact_gas_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "flow_code": ["EXPORTS"],
            "product_code": ["NATURAL_GAS"],
            "unit_code": ["M_M3"],
        },
        "mode": "annual_share",
        "period_from": "2024",
        "annual_share_target": "latest_available",
        "annual_share_year_label": "{year} г.",
        "round_digits": 1,
        "value_scale": 0.001,
        "top_n_rows": 10,
        "drop_empty_top_rows": True,
        "annual_share_total_partner": "TOTAL",
        "annual_share_total_product": "NATURAL_GAS",
        "country_scope": "oecd",
    },
    "gas-lng-export-by-partners": {
        "domain": "gas",
        "title": "Экспорт СПГ из страны ОЭСР по направлениям, (млрд м³)",
        "fact_table": "gas.fact_gas_trade",
        "frequency_code": "A",
        "row_dimension": ["partner_country_code", "partner_code"],
        "base_filters": {"flow_code": ["EXPORTS"]},
        "mode": "annual_share",
        "top_n_rows": 10,
        "country_scope": "oecd",
    },
    "gas-oecd-consumption": {
        "domain": "gas",
        "title": "Потребление газа в стране ОЭСР, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "M",
        "row_dimension": None,
        "base_filters": {"flow_code": ["GRDEL_INLAND_OBS"]},
        "mode": "monthly_with_yoy",
        "period_from": "2020",
        "latest_period_label": "мес.-5 {year}",
        "pct_label": "% к мес.-5 {prev_year}",
        "country_scope": "oecd",
    },
    "gas-oecd-consumption-by-sectors": {
        "domain": "gas",
        "title": "Потребление газа в стране ОЭСР по секторам, (млрд м³)",
        "fact_table": "gas.fact_gas_balance",
        "frequency_code": "A",
        "row_dimension": "flow_code",
        "base_filters": {},
        "mode": "annual_share",
        "country_scope": "oecd",
    },
    "coal-balance-production": {
        "domain": "coal",
        "title": "Добыча угля в стране, (тыс. тонн)",
        "fact_table": "coal.fact_coal_balance",
        "frequency_code": "A",
        "row_dimension": "product_code",
        "base_filters": {
            "flow_code": ["INDPROD"],
            "unit_code": ["KT"],
        },
        "mode": "annual_series",
        "period_from": "2018",
    },
    "coal-trade-import-partners": {
        "domain": "coal",
        "title": "Импорт угля по партнёрам, (тыс. тонн)",
        "fact_table": "coal.fact_coal_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "flow_code": ["IMPORTS"],
            "unit_code": ["KT"],
        },
        "mode": "annual_share",
        "period_from": "2018",
    },
    "electricity-generation-by-fuel": {
        "domain": "electricity",
        "title": "Генерация электроэнергии по видам топлива, (ГВт·ч)",
        "fact_table": "electricity.fact_electricity_generation",
        "frequency_code": "A",
        "row_dimension": "product_code",
        "base_filters": {
            "indicator_code": ["GENERATION"],
            "unit_code": ["GWH"],
        },
        "mode": "annual_series",
        "period_from": "2018",
    },
    "electricity-trade-partners": {
        "domain": "electricity",
        "title": "Импорт/экспорт электроэнергии по партнёрам, (ГВт·ч)",
        "fact_table": "electricity.fact_electricity_trade",
        "frequency_code": "A",
        "row_dimension": "partner_code",
        "base_filters": {
            "unit_code": ["GWH"],
        },
        "mode": "annual_share",
        "period_from": "2018",
    },
}

OIL_PRODUCT_WHITELISTS: dict[str, list[str]] = {
    "oil": [
        "ADDITIVE",
        "NGL",
        "CONDENSATE",
        "NONCONV_OILS",
        "CRUDEOIL",
        "NONCRUDE",
        "REFFEEDS",
    ],
    "products": [
        "MOTORGAS",
        "NONBIOGASO",
        "AVGAS",
        "JETGAS",
        "JETKERO",
        "NONBIOJETK",
        "BIOJET_KER",
        "HEATOIL",
        "RESFUEL",
        "FUELOIL_HS",
        "LOWSULF",
        "REFINGAS",
        "NAPHTHA",
        "OTHKERO",
        "LPG",
        "BITUMEN",
        "PETCOKE",
        "PARWAX",
        "LUBRIC",
        "BIOFUELS",
        "LIQBIOFUEL",
        "BIOGASOL",
        "BIODIESEL",
    ],
    "crude": [
        "CRUDEOIL",
        "CONDENSATE",
        "NONCONV_OILS",
        "NGL",
        "ETHANE",
        "REFFEEDS",
    ],
}

GUIDE_TEMPLATE_PRODUCT_GROUP: dict[str, str] = {
    "oil-oecd-oil-import-by-partners": "crude",
    "oil-oecd-oil-export-by-partners": "crude",
    "oil-oecd-refinery-throughput": "crude",
    "oil-oecd-products-production": "products",
    "oil-oecd-products-production-structure": "products",
    "oil-oecd-products-consumption": "products",
    "oil-oecd-products-consumption-by-sector": "products",
    "oil-oecd-products-export": "products",
    "oil-nonoecd-products-export": "products",
    "oil-oecd-products-import": "products",
    "oil-nonoecd-products-import": "products",
    "oil-nonoecd-products-consumption": "products",
    "oil-nonoecd-products-production": "products",
    "oil-oecd-products-import-by-partners": "products",
    "oil-oecd-products-export-by-partners": "products",
    "oil-oecd-crude-production-tonnes": "crude",
    "oil-nonoecd-crude-production-tonnes": "crude",
    "oil-oecd-crude-field-production": "crude",
    "oil-oecd-crude-import": "crude",
    "oil-oecd-crude-export": "crude",
}

TECHNICAL_COLUMNS = {"id", "load_batch_id", "created_at", "updated_at", "time_period_start"}


def list_allowed_fact_tables() -> list[str]:
    domains = ("oil", "gas", "coal", "electricity")
    return [
        table.table
        for domain in domains
        for table in TABLES_BY_DOMAIN[domain]
        if table.table_type == "fact"
    ]


async def get_table_columns(table_name: str) -> set[str]:
    pool = get_pool()
    table_schema, simple_table = table_name.split(".", 1)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            """,
            table_schema,
            simple_table,
        )
    return {row["column_name"] for row in rows}


def map_filterable_columns(columns: set[str]) -> list[dict[str, str]]:
    candidates = [
        ("country_code", "Страны"),
        ("reporter_code", "Страны (репортер)"),
        ("partner_code", "Страны (партнер)"),
        ("partner_country_code", "Страны (партнер)"),
        ("flow_code", "Потоки"),
        ("ncv_flow_code", "NCV-потоки"),
        ("product_code", "Продукты"),
        ("frequency_code", "Период"),
        ("unit_code", "Единицы"),
        ("source_id", "Источники"),
        ("field_code", "Месторождения"),
        ("plant_type_code", "Типы станций"),
        ("indicator_code", "Индикаторы"),
        ("environment", "Среда"),
        ("stock_type", "Тип запасов"),
        ("qualifier", "Квалификатор"),
        ("conf_status", "Конфиденциальность"),
        ("data_status", "Статус данных"),
    ]
    return [{"key": key, "label": label} for key, label in candidates if key in columns]


async def fetch_hierarchy(
    table_name: str,
    code_col: str,
    name_ru_col: str,
    name_en_col: str,
    parent_col: str,
) -> list[dict[str, Any]]:
    pool = get_pool()
    query = f"""
        WITH RECURSIVE hierarchy AS (
            SELECT
                {code_col} AS code,
                COALESCE(NULLIF({name_ru_col}, ''), {name_en_col}) AS name,
                {parent_col} AS parent_code,
                0::int AS depth
            FROM {table_name}
            WHERE {parent_col} IS NULL
            UNION ALL
            SELECT
                child.{code_col} AS code,
                COALESCE(NULLIF(child.{name_ru_col}, ''), child.{name_en_col}) AS name,
                child.{parent_col} AS parent_code,
                parent.depth + 1 AS depth
            FROM {table_name} child
            JOIN hierarchy parent ON child.{parent_col} = parent.code
        )
        SELECT code, name, parent_code, depth
        FROM hierarchy
        ORDER BY depth, name;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(row) for row in rows]


async def fetch_flat_reference(
    table_name: str,
    code_col: str,
    name_ru_col: str,
    name_en_col: str,
) -> list[dict[str, Any]]:
    pool = get_pool()
    query = f"""
        SELECT
            {code_col} AS code,
            COALESCE(NULLIF({name_ru_col}, ''), {name_en_col}) AS name,
            NULL::varchar AS parent_code,
            0::int AS depth
        FROM {table_name}
        ORDER BY name
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(row) for row in rows]


async def fetch_distinct_from_table(table_name: str, column: str) -> list[dict[str, Any]]:
    pool = get_pool()
    query = f"""
        SELECT
            {column}::text AS code,
            {column}::text AS name,
            NULL::varchar AS parent_code,
            0::int AS depth
        FROM {table_name}
        WHERE {column} IS NOT NULL
        GROUP BY {column}
        ORDER BY {column}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(row) for row in rows]


def build_where_clause(
    selected_filter_values: dict[str, list[str]],
    allowed_filter_columns: set[str],
    skip_key: str | None = None,
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1
    for key, values in selected_filter_values.items():
        if key == skip_key or key not in allowed_filter_columns or not values:
            continue
        conditions.append(f"t.{key}::text = ANY(${idx}::text[])")
        params.append(values)
        idx += 1
    if not conditions:
        return "", params
    return "WHERE " + " AND ".join(conditions), params


def determine_category_keys(
    rows: list[dict[str, Any]],
    filter_values: dict[str, list[str]],
    available_filter_keys: list[str] | None = None,
) -> list[str]:
    if not rows:
        return []

    selected_keys = [key for key, values in filter_values.items() if values and key in rows[0]]
    if available_filter_keys:
        # If a filter has no explicit selection, keep it in categories too,
        # so values are shown separately instead of being aggregated into sum.
        remaining_keys = [
            key for key in available_filter_keys if key in rows[0] and key not in selected_keys
        ]
        category_keys = [*selected_keys, *remaining_keys]
    else:
        category_keys = selected_keys or ["country_code", "flow_code", "product_code"]
        category_keys = [key for key in category_keys if key in rows[0]]

    if "unit_code" in rows[0] and "unit_code" not in category_keys:
        category_keys.append("unit_code")
    if not category_keys:
        category_keys = ["country_code"] if "country_code" in rows[0] else []
        if "unit_code" in rows[0] and "unit_code" not in category_keys:
            category_keys.append("unit_code")
    return category_keys


async def fetch_filter_nodes(fact_table: str, key: str) -> list[dict[str, Any]]:
    if key == "qualifier":
        return build_static_nodes(QUALIFIER_LABELS)
    if key == "conf_status":
        return build_static_nodes(CONF_STATUS_LABELS)
    if key in {"country_code", "reporter_code", "partner_code", "partner_country_code"}:
        return await fetch_hierarchy(
            table_name="base.ref_country",
            code_col="country_code",
            name_ru_col="country_name_ru",
            name_en_col="country_name",
            parent_col="parent_code",
        )
    if key == "flow_code":
        return await fetch_hierarchy(
            table_name="base.ref_energy_flow",
            code_col="flow_code",
            name_ru_col="flow_name_ru",
            name_en_col="flow_name",
            parent_col="parent_code",
        )
    if key == "ncv_flow_code":
        return await fetch_hierarchy(
            table_name="coal.ref_coal_ncv_flow",
            code_col="ncv_flow_code",
            name_ru_col="ncv_flow_name_ru",
            name_en_col="ncv_flow_name",
            parent_col="parent_code",
        )
    if key == "product_code":
        if fact_table.startswith("oil."):
            product_table = "oil.ref_oil_product"
        elif fact_table.startswith("gas."):
            product_table = "gas.ref_gas_product"
        elif fact_table.startswith("electricity."):
            product_table = "electricity.ref_electricity_product"
        else:
            product_table = "coal.ref_coal_product"
        return await fetch_hierarchy(
            table_name=product_table,
            code_col="product_code",
            name_ru_col="product_name_ru",
            name_en_col="product_name",
            parent_col="parent_code",
        )
    if key == "plant_type_code":
        return await fetch_hierarchy(
            table_name="electricity.ref_electricity_plant_type",
            code_col="plant_type_code",
            name_ru_col="plant_type_name_ru",
            name_en_col="plant_type_name",
            parent_col="parent_code",
        )
    if key == "indicator_code":
        return await fetch_flat_reference(
            table_name="electricity.ref_electricity_indicator",
            code_col="indicator_code",
            name_ru_col="indicator_name_ru",
            name_en_col="indicator_name",
        )
    if key == "frequency_code":
        return await fetch_flat_reference(
            table_name="base.ref_frequency",
            code_col="frequency_code",
            name_ru_col="frequency_name_ru",
            name_en_col="frequency_name",
        )
    if key == "unit_code":
        return await fetch_flat_reference(
            table_name="base.ref_unit",
            code_col="unit_code",
            name_ru_col="unit_name_ru",
            name_en_col="unit_name",
        )
    if key == "source_id":
        return await fetch_flat_reference(
            table_name="base.ref_data_source",
            code_col="source_id::text",
            name_ru_col="source_name",
            name_en_col="source_name",
        )
    if key == "field_code":
        return await fetch_flat_reference(
            table_name="oil.ref_oil_field",
            code_col="field_code",
            name_ru_col="field_name",
            name_en_col="field_name",
        )
    return await fetch_distinct_from_table(fact_table, key)


def build_value_label_map(nodes: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(node.get("code")): str(node.get("name"))
        for node in nodes
        if node.get("code") is not None
    }


def build_static_nodes(mapping: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"code": code, "name": name, "parent_code": None, "depth": 0}
        for code, name in mapping.items()
    ]


def _period_sort_key(value: str) -> tuple[int, int, int]:
    year_match = re.fullmatch(r"(\d{4})", value)
    if year_match:
        return (int(year_match.group(1)), 0, 0)
    parsed = _parse_month_period(value)
    if parsed:
        return (parsed[0], parsed[1], 0)
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", value, flags=re.IGNORECASE)
    if quarter_match:
        return (int(quarter_match.group(1)), int(quarter_match.group(2)) * 3, 0)
    return (9999, 99, 99)


def _period_year(value: str) -> str | None:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else None


def _previous_year_same_period(period: str) -> str | None:
    parsed = _parse_month_period(period)
    if parsed:
        year, month = parsed
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
            return f"{year - 1:04d}-{month:02d}-01"
        return f"{year - 1:04d}-{month:02d}"
    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", period, flags=re.IGNORECASE)
    if quarter_match:
        return f"{int(quarter_match.group(1)) - 1:04d}-Q{quarter_match.group(2)}"
    year_match = re.fullmatch(r"(\d{4})", period)
    if year_match:
        return f"{int(year_match.group(1)) - 1:04d}"
    return None


def _days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def _days_in_period(period: str) -> int | None:
    parsed = _parse_month_period(period)
    if parsed:
        year, month = parsed
        if month < 1 or month > 12:
            return None
        return calendar.monthrange(year, month)[1]

    quarter_match = re.fullmatch(r"(\d{4})-Q([1-4])", period, flags=re.IGNORECASE)
    if quarter_match:
        year = int(quarter_match.group(1))
        quarter = int(quarter_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        return sum(calendar.monthrange(year, month)[1] for month in range(start_month, start_month + 3))

    year_match = re.fullmatch(r"(\d{4})", period)
    if year_match:
        return _days_in_year(int(year_match.group(1)))

    return None


async def _load_bbl_t_conversion_map(
    product_codes: set[str],
) -> tuple[dict[tuple[int, str], float], dict[int, float], float | None]:
    normalized_products = sorted(
        {
            str(code)
            for code in product_codes
            if code and str(code).strip() and str(code).upper() != "N/A"
        }
    )
    requested_products = sorted(set([*_resolve_product_codes(normalized_products), "CRUDE_OIL"]))
    if not requested_products:
        return ({}, {}, None)

    pool = get_pool()
    query = """
        SELECT
            product_code::text AS product_code,
            time_period::text AS time_period,
            AVG(value::double precision) AS conversion_value
        FROM oil.fact_oil_conversion
        WHERE unit_code::text = 'BBL_T'
          AND value IS NOT NULL
          AND product_code::text = ANY($1::text[])
        GROUP BY product_code::text, time_period::text
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, requested_products)

    conversion_map: dict[tuple[int, str], float] = {}
    crude_by_year: dict[int, float] = {}
    latest_crude_year = -1
    latest_crude: float | None = None

    for row in rows:
        product_code = str(row["product_code"])
        period = str(row["time_period"])
        year = _period_year(period)
        if year is None:
            continue
        year_int = int(year)
        conversion_value = float(row["conversion_value"])
        if conversion_value <= 0:
            continue

        conversion_map[(year_int, product_code)] = conversion_value
        if product_code == "CRUDE_OIL":
            crude_by_year[year_int] = conversion_value
            if year_int > latest_crude_year:
                latest_crude_year = year_int
                latest_crude = conversion_value

    return (conversion_map, crude_by_year, latest_crude)


def _resolve_bbl_t_conversion(
    *,
    year: int,
    product_code: str,
    conversion_map: dict[tuple[int, str], float],
    crude_by_year: dict[int, float],
    latest_crude: float | None,
) -> float | None:
    resolved_code = LEGACY_OIL_PRODUCT_CODES.get(product_code, product_code)
    direct = conversion_map.get((year, resolved_code))
    if direct and direct > 0:
        return direct
    direct_legacy = conversion_map.get((year, product_code))
    if direct_legacy and direct_legacy > 0:
        return direct_legacy
    crude_for_year = crude_by_year.get(year)
    if crude_for_year and crude_for_year > 0:
        return crude_for_year
    if latest_crude and latest_crude > 0:
        return latest_crude
    return None


async def _resolve_country_filter_key(fact_table: str) -> str | None:
    columns = await get_table_columns(fact_table)
    if "country_code" in columns:
        return "country_code"
    if "reporter_code" in columns:
        return "reporter_code"
    return None


async def _resolve_country_scope(country_code: str) -> str | None:
    pool = get_pool()
    query = """
        WITH RECURSIVE parents AS (
            SELECT
                country_code::text AS code,
                parent_code::text AS parent_code
            FROM base.ref_country
            WHERE UPPER(country_code::text) = UPPER($1)
            UNION ALL
            SELECT
                p.country_code::text AS code,
                p.parent_code::text AS parent_code
            FROM base.ref_country p
            JOIN parents c ON UPPER(c.parent_code) = UPPER(p.country_code::text)
        ),
        oecd_tree AS (
            SELECT country_code::text AS code
            FROM base.ref_country
            WHERE country_code::text IN ('TOTOECD', 'OECDTOT')
            UNION ALL
            SELECT c.country_code::text AS code
            FROM base.ref_country c
            JOIN oecd_tree p ON c.parent_code::text = p.code
        )
        SELECT
            EXISTS(
                SELECT 1
                FROM base.ref_country
                WHERE UPPER(country_code::text) = UPPER($1)
            ) AS country_exists,
            EXISTS(
                SELECT 1
                FROM oecd_tree
                WHERE UPPER(code) = UPPER($1)
            ) AS is_oecd,
            COALESCE(
                ARRAY(
                    SELECT UPPER(code)
                    FROM parents
                ),
                ARRAY[]::text[]
            ) AS lineage_codes
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, country_code)

    if not row:
        return None

    lineage_codes = {str(code) for code in (row["lineage_codes"] or [])}
    is_oecd_marker = any(
        code in OECD_ROOT_CODES or code.startswith("OECD")
        for code in lineage_codes
    )
    is_non_oecd_marker = any(
        code == "TOTNONOECD"
        or code.startswith("NONOECD")
        or code.startswith("NON_OECD")
        for code in lineage_codes
    )

    if bool(row["is_oecd"]) or is_oecd_marker:
        return "oecd"
    if is_non_oecd_marker:
        return "non_oecd"
    if bool(row["country_exists"]):
        # If hierarchy doesn't clearly indicate OECD/non-OECD,
        # skip strict scope blocking to avoid false-empty tables.
        return None
    return None


async def _country_matches_required_scope(country_code: str, required_scope: str) -> bool:
    actual_scope = await _resolve_country_scope(country_code)
    if actual_scope == required_scope:
        return True
    if actual_scope is not None:
        return False

    pool = get_pool()
    async with pool.acquire() as conn:
        is_oecd = await conn.fetchval(
            """
            WITH RECURSIVE oecd_tree AS (
                SELECT country_code::text AS code
                FROM base.ref_country
                WHERE country_code::text IN ('TOTOECD', 'OECDTOT')
                UNION ALL
                SELECT c.country_code::text AS code
                FROM base.ref_country c
                JOIN oecd_tree p ON c.parent_code::text = p.code
            )
            SELECT EXISTS(
                SELECT 1 FROM oecd_tree WHERE UPPER(code) = UPPER($1)
            )
            """,
            country_code,
        )
    if required_scope == "oecd":
        return bool(is_oecd)
    if required_scope == "non_oecd":
        return not bool(is_oecd)
    return True


def _guide_report_month_cap(*, current_month: int, latest_available_month: int | None) -> int | None:
    if latest_available_month is None:
        return None
    capped_month = max(1, current_month - 4)
    return min(latest_available_month, capped_month)


def _is_guide_response_empty(columns: list[str], rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return True
    value_columns = [column for column in columns if column != "Показатель"]
    if not value_columns:
        return True
    for row in rows:
        if any(not _is_zero_like_guide_value(row.get(column)) for column in value_columns):
            return False
    return True


async def _resolve_row_label_map(fact_table: str, row_dimension: str | None) -> dict[str, str]:
    if not row_dimension:
        return {}
    nodes = await fetch_filter_nodes(fact_table=fact_table, key=row_dimension)
    return build_value_label_map(nodes)


async def _resolve_non_aggregate_country_codes(
    fact_table: str,
    row_dimension: str | None,
) -> set[str] | None:
    if row_dimension not in {"country_code", "reporter_code", "partner_country_code", "partner_code"}:
        return None

    nodes = await fetch_filter_nodes(fact_table=fact_table, key=row_dimension)
    if not nodes:
        return None

    child_parent_codes = {
        str(node.get("parent_code"))
        for node in nodes
        if node.get("parent_code")
    }
    allowed_codes = {
        str(node.get("code"))
        for node in nodes
        if node.get("code")
        and node.get("parent_code") is not None
        and str(node.get("code")) not in child_parent_codes
    }
    return allowed_codes if allowed_codes else None


def _build_annual_series_rows(
    row_period_values: dict[str, dict[str, float]],
    row_labels: list[str],
    start_year: int,
    end_year: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    periods = [str(year) for year in range(start_year, end_year + 1)]
    rows: list[dict[str, Any]] = []
    for row_label in row_labels:
        values = row_period_values.get(row_label, {})
        payload: dict[str, Any] = {"Показатель": row_label}
        for period in periods:
            period_values = [
                metric
                for period_key, metric in values.items()
                if _period_year(period_key) == period
            ]
            payload[period] = sum(period_values) if period_values else None
        rows.append(payload)
    return (["Показатель", *periods], rows)


def _build_annual_share_rows(
    row_period_values: dict[str, dict[str, float]],
    row_labels: list[str],
    target_year: int,
    top_n_rows: int | None = None,
    drop_empty_top_rows: bool = False,
    year_label: str = "Год-2",
    round_digits: int | None = None,
    total_partner_label: str | None = None,
    total_partner_period_values: dict[str, float] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    target_year_label = str(target_year)
    period_label = year_label
    row_totals: dict[str, float | None] = {}
    for row_label in row_labels:
        if row_label.strip().lower() == "итого" and row_label != total_partner_label:
            continue
        period_values = [
            metric
            for period_key, metric in row_period_values.get(row_label, {}).items()
            if _period_year(period_key) == target_year_label
        ]
        row_totals[row_label] = sum(period_values) if period_values else None

    ranked_source = {
        label: value
        for label, value in row_totals.items()
        if total_partner_label is None or label != total_partner_label
    }
    total_from_partner: float | None = None
    if total_partner_period_values:
        partner_period_values = [
            metric
            for period_key, metric in total_partner_period_values.items()
            if _period_year(period_key) == target_year_label
        ]
        if partner_period_values:
            total_from_partner = float(sum(partner_period_values))

    if total_from_partner is not None:
        total = total_from_partner
        has_any_values = True
    elif total_partner_label and total_partner_label in row_totals:
        total = row_totals.get(total_partner_label)
        has_any_values = total is not None
    else:
        total = sum(value for value in ranked_source.values() if value is not None)
        has_any_values = any(value is not None for value in ranked_source.values())

    output_labels = list(row_labels)
    if top_n_rows and top_n_rows > 0:
        ranked_labels = sorted(
            ranked_source.items(),
            key=lambda item: (
                item[1] is None,
                -(item[1] or 0.0),
                item[0].lower(),
            ),
        )
        if drop_empty_top_rows:
            ranked_labels = [(label, value) for label, value in ranked_labels if value is not None]
        output_labels = [label for label, _ in ranked_labels[:top_n_rows]]

    rows: list[dict[str, Any]] = []
    for row_label in output_labels:
        if total_partner_label and row_label == total_partner_label:
            continue
        value = row_totals.get(row_label)
        if value is None:
            share: float | None = None
        elif total:
            share = value / total * 100.0
        else:
            share = 0.0
        rounded_value = _round_guide_number(value, round_digits) if round_digits is not None else value
        rounded_share = _round_guide_number(share, round_digits) if round_digits is not None else share
        rows.append(
            {
                "Показатель": row_label,
                period_label: rounded_value,
                "Доля в структуре": rounded_share,
            }
        )
    if total_from_partner is not None:
        total_value = total_from_partner
    elif total_partner_label and total_partner_label in row_totals:
        total_value = row_totals.get(total_partner_label)
    else:
        total_value = total if has_any_values else None
    total_share = (100.0 if total_value else 0.0) if has_any_values else None
    if round_digits is not None:
        total_value = _round_guide_number(total_value, round_digits)
        total_share = _round_guide_number(total_share, round_digits)
    rows.append(
        {
            "Показатель": "Итого",
            period_label: total_value,
            "Доля в структуре": total_share,
        }
    )
    return (["Показатель", period_label, "Доля в структуре"], rows)


def _build_monthly_with_yoy_rows(
    row_period_values: dict[str, dict[str, float]],
    row_labels: list[str],
    start_year: int,
    latest_period_label: str,
    pct_label: str,
    annualize_partial_year: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    monthly_periods = sorted(
        {
            period
            for values in row_period_values.values()
            for period in values.keys()
            if _parse_month_period(period) is not None
        },
        key=_period_sort_key,
    )
    current_year = datetime.now().year
    annual_periods = [str(year) for year in range(start_year, current_year)]
    latest_period = monthly_periods[-1] if monthly_periods else (annual_periods[-1] if annual_periods else "")

    rows: list[dict[str, Any]] = []
    for row_label in row_labels:
        period_values = row_period_values.get(row_label, {})
        annual_totals: dict[str, float] = defaultdict(float)
        annual_days_covered: dict[str, int] = defaultdict(int)
        for period, value in period_values.items():
            year = _period_year(period)
            if not year:
                continue
            annual_totals[year] += value
            period_days = _days_in_period(period)
            if period_days is not None:
                annual_days_covered[year] += period_days

        payload: dict[str, Any] = {"Показатель": row_label}
        for year in annual_periods:
            if year not in annual_totals:
                payload[year] = None
                continue
            annual_value = annual_totals[year]
            if annualize_partial_year:
                year_days = _days_in_year(int(year))
                covered_days = annual_days_covered.get(year, 0)
                if covered_days > 0 and covered_days < year_days:
                    annual_value = annual_value / covered_days * year_days
            payload[year] = annual_value

        latest_value = _lookup_period_value(period_values, latest_period) if latest_period else None
        previous_period = _previous_year_same_period(latest_period) if latest_period else None
        previous_value = (
            _lookup_period_value(period_values, previous_period) if previous_period else None
        )
        pct_value: float | None = None
        if latest_value is not None and previous_value not in (None, 0):
            pct_value = (latest_value - previous_value) / previous_value * 100.0
        payload[latest_period_label] = latest_value
        payload[pct_label] = pct_value
        rows.append(payload)

    columns = ["Показатель", *annual_periods]
    if latest_period_label not in columns:
        columns.append(latest_period_label)
    columns.append(pct_label)
    return (columns, rows)


def _build_empty_guide_columns(
    mode: str,
    start_year: int,
    current_year: int,
    latest_period_label: str,
    pct_label: str,
) -> list[str]:
    if mode == "annual_share":
        return ["Показатель", "Год-2", "Доля в структуре"]
    if mode == "tz_oecd_products_structure":
        return ["Показатель", f"{current_year - 1} г.", "Доля в структуре"]
    if mode in {
        "tz_oecd_crude_production",
        "tz_nonoecd_crude_production",
        "tz_oecd_field_production",
        "tz_oecd_products_consumption",
    }:
        annual_periods = [str(year) for year in range(start_year, current_year)]
        return ["Показатель", *annual_periods, latest_period_label, pct_label]
    if mode == "tz_nonoecd_world_supply_annual":
        annual_periods = [str(year) for year in range(start_year, current_year)]
        return ["Показатель", *annual_periods]
    if mode == "monthly_with_yoy":
        annual_periods = [str(year) for year in range(start_year, current_year)]
        columns = ["Показатель", *annual_periods]
        if latest_period_label not in columns:
            columns.append(latest_period_label)
        columns.append(pct_label)
        return columns
    annual_periods = [str(year) for year in range(start_year, current_year - 1)]
    return ["Показатель", *annual_periods]


def _is_zero_like_guide_value(value: Any) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, (int, float)):
        return abs(float(value)) < 1e-12
    return False


def _filter_zero_rows_for_production_tables(
    *,
    title: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if "добыча" not in title.lower():
        return rows

    value_columns = [column for column in columns if column != "Показатель"]
    if not value_columns:
        return rows

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if any(not _is_zero_like_guide_value(row.get(column)) for column in value_columns):
            filtered_rows.append(row)
    return filtered_rows


def _round_guide_number(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _scale_guide_number(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    return float(value) * scale


async def _fetch_guide_aggregate_period_values(
    *,
    source_template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
) -> dict[str, float]:
    fact_table = str(source_template.get("fact_table") or default_fact_table)
    source_filters = {
        key: list(values)
        for key, values in dict(source_template.get("base_filters", {})).items()
    }
    frequency_code = source_template.get("frequency_code")
    if frequency_code:
        source_filters["frequency_code"] = [str(frequency_code)]

    country_filter_key = default_country_filter_key
    if fact_table != default_fact_table:
        country_filter_key = await _resolve_country_filter_key(fact_table)
    if country_code and country_filter_key:
        source_filters[country_filter_key] = [country_code]

    source_filters = _expand_guide_tonne_unit_filters(source_filters)
    source_filters = _normalize_guide_filters(source_filters)

    columns_set = await get_table_columns(fact_table)
    allowed_filter_columns = {spec["key"] for spec in map_filterable_columns(columns_set)}
    where_sql, query_params = build_where_clause(
        selected_filter_values=source_filters,
        allowed_filter_columns=allowed_filter_columns,
    )
    if "source_id" in columns_set:
        source_select = "COALESCE(t.source_id::text, 'N/A') AS source_key,"
        query = f"""
            SELECT
                period_key,
                MAX(metric_value)::double precision AS metric_value
            FROM (
                SELECT
                    COALESCE(t.time_period::text, 'N/A') AS period_key,
                    {source_select}
                    MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
                FROM {fact_table} t
                {where_sql}
                GROUP BY period_key, source_key
            ) source_rows
            GROUP BY period_key
        """
    else:
        query = f"""
            SELECT
                COALESCE(t.time_period::text, 'N/A') AS period_key,
                MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
            FROM {fact_table} t
            {where_sql}
            GROUP BY period_key
        """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *query_params)

    period_values: dict[str, float] = {}
    period_from = source_template.get("period_from")
    from_key = (
        _period_sort_key(str(period_from))
        if isinstance(period_from, str) and period_from.strip()
        else None
    )
    for row in rows:
        period_key = str(row["period_key"])
        if from_key is not None and _period_sort_key(period_key) < from_key:
            continue
        period_values[period_key] = float(row["metric_value"] or 0.0)
    return period_values


def _collect_guide_annual_years(period_map_by_code: dict[str, dict[str, float]]) -> set[int]:
    years: set[int] = set()
    for values in period_map_by_code.values():
        for period_key in values.keys():
            period_year = _period_year(period_key)
            if period_year and period_year.isdigit():
                years.add(int(period_year))
    return years


def _sum_for_codes_at_period(
    period_map_by_code: dict[str, dict[str, float]],
    product_codes: list[str],
    period_key: str,
) -> float | None:
    values: list[float] = []
    for code in product_codes:
        period_values = period_map_by_code.get(code, {})
        value = _lookup_period_value(period_values, period_key)
        if value is None:
            for stored_period, stored_value in period_values.items():
                if _period_year(stored_period) == period_key:
                    value = stored_value
                    break
        if value is not None:
            values.append(value)
    if not values:
        return None
    return float(sum(values))


def _sum_for_codes_at_periods(
    period_map_by_code: dict[str, dict[str, float]],
    product_codes: list[str],
    period_keys: list[str],
) -> float | None:
    values: list[float] = []
    for period_key in period_keys:
        value = _sum_for_codes_at_period(period_map_by_code, product_codes, period_key)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return float(sum(values))


def _sum_codes_for_year_months(
    period_map_by_code: dict[str, dict[str, float]],
    product_codes: list[str],
    year: int,
    months: range | list[int],
) -> float | None:
    values: list[float] = []
    for month in months:
        period_key = f"{year:04d}-{month:02d}"
        value = _sum_for_codes_at_period(period_map_by_code, product_codes, period_key)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return float(sum(values))


GUIDE_TONNE_UNIT_CODES = ("KT", "KB")
GUIDE_TONNE_UNIT_PRIORITY = {"KT": 0, "KB": 1}
GUIDE_QUALIFIER_PRIORITY = {"A": 0, "I": 1}


def _resolve_qualifier_priority(template: dict[str, Any]) -> dict[str, int]:
    custom = template.get("qualifier_priority")
    if isinstance(custom, list):
        return {str(item).upper(): index for index, item in enumerate(custom)}
    if isinstance(custom, dict):
        return {str(key).upper(): int(value) for key, value in custom.items()}
    return GUIDE_QUALIFIER_PRIORITY


def _expand_guide_tonne_unit_filters(filters: dict[str, list[str]]) -> dict[str, list[str]]:
    expanded = {key: list(values) for key, values in filters.items()}
    unit_codes = expanded.get("unit_code")
    if unit_codes == ["KT"]:
        expanded["unit_code"] = list(GUIDE_TONNE_UNIT_CODES)
    return expanded


def _select_guide_tonne_volume(entries: list[tuple[str, float]]) -> float | None:
    if not entries:
        return None
    by_unit: dict[str, float] = defaultdict(float)
    for unit_code, value in entries:
        by_unit[str(unit_code).upper()] += value
    for preferred_unit in sorted(GUIDE_TONNE_UNIT_PRIORITY, key=GUIDE_TONNE_UNIT_PRIORITY.get):
        if preferred_unit in by_unit:
            return by_unit[preferred_unit]
    return float(sum(by_unit.values()))


def _finalize_guide_period_map(
  staged_values: dict[tuple[str, str], list[tuple[str, str, float]]],
  *,
  prefer_qualifier: bool,
  qualifier_priority: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    priority = qualifier_priority or GUIDE_QUALIFIER_PRIORITY
    period_map_by_code: dict[str, dict[str, float]] = defaultdict(dict)
    for (code, period_key), entries in staged_values.items():
        if prefer_qualifier:
            by_qualifier: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for qualifier_key, unit_key, value in entries:
                by_qualifier[str(qualifier_key).upper()].append((unit_key, value))
            selected_qualifier = min(
                by_qualifier.keys(),
                key=lambda item: priority.get(item, 99),
            )
            selected_value = _select_guide_tonne_volume(by_qualifier[selected_qualifier])
        else:
            selected_value = _select_guide_tonne_volume(
                [(unit_key, value) for _, unit_key, value in entries]
            )
        if selected_value is None:
            continue
        period_map_by_code[code][period_key] = selected_value
    return period_map_by_code


def _full_month_years(period_map_by_code: dict[str, dict[str, float]], current_year: int) -> set[int]:
    months_by_year: dict[int, set[int]] = defaultdict(set)
    for values in period_map_by_code.values():
        for period_key in values.keys():
            month_parsed = _parse_month_period(period_key)
            if not month_parsed:
                continue
            year, month = month_parsed
            if year >= current_year:
                continue
            months_by_year[year].add(month)
    return {year for year, months in months_by_year.items() if len(months) == 12}


async def _fetch_guide_source_period_values(
    *,
    source_template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    prefer_qualifier: bool = False,
    qualifier_priority: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    fact_table = str(source_template.get("fact_table") or default_fact_table)
    source_filters = {
        key: list(values)
        for key, values in dict(source_template.get("base_filters", {})).items()
    }
    frequency_code = source_template.get("frequency_code")
    if frequency_code:
        source_filters["frequency_code"] = [str(frequency_code)]

    country_filter_key = default_country_filter_key
    if fact_table != default_fact_table:
        country_filter_key = await _resolve_country_filter_key(fact_table)
    if country_code and country_filter_key:
        source_filters[country_filter_key] = [country_code]

    source_filters = _expand_guide_tonne_unit_filters(source_filters)
    source_filters = _normalize_guide_filters(source_filters)

    columns_set = await get_table_columns(fact_table)
    if "product_code" not in columns_set:
        return {}
    allowed_filter_columns = {spec["key"] for spec in map_filterable_columns(columns_set)}
    where_sql, query_params = build_where_clause(
        selected_filter_values=source_filters,
        allowed_filter_columns=allowed_filter_columns,
    )
    unit_select = (
        "COALESCE(t.unit_code::text, 'N/A') AS unit_key,"
        if "unit_code" in columns_set
        else "'KT'::text AS unit_key,"
    )
    qualifier_select = (
        "COALESCE(t.qualifier::text, 'N/A') AS qualifier_key,"
        if prefer_qualifier and "qualifier" in columns_set
        else "'A'::text AS qualifier_key,"
    )
    unit_group = ", unit_key" if "unit_code" in columns_set else ""
    qualifier_group = ", qualifier_key" if prefer_qualifier and "qualifier" in columns_set else ""
    source_group = ", source_key" if "source_id" in columns_set else ""
    source_select = (
        "COALESCE(t.source_id::text, 'N/A') AS source_key,"
        if "source_id" in columns_set
        else "'N/A'::text AS source_key,"
    )
    partner_in_table = "partner_code" in columns_set
    partner_select = (
        "COALESCE(t.partner_code::text, 'N/A') AS partner_key,"
        if partner_in_table
        else ""
    )
    partner_group = ", partner_key" if partner_in_table else ""
    if "source_id" in columns_set:
        if partner_in_table and "partner_code" not in source_filters:
            query = f"""
                SELECT
                    product_key,
                    unit_key,
                    qualifier_key,
                    period_key,
                    MAX(metric_value)::double precision AS metric_value
                FROM (
                    SELECT
                        product_key,
                        unit_key,
                        qualifier_key,
                        period_key,
                        source_key,
                        SUM(metric_value)::double precision AS metric_value
                    FROM (
                        SELECT
                            COALESCE(t.product_code::text, 'N/A') AS product_key,
                            {unit_select}
                            {qualifier_select}
                            {source_select}
                            {partner_select}
                            COALESCE(t.time_period::text, 'N/A') AS period_key,
                            MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
                        FROM {fact_table} t
                        {where_sql}
                        GROUP BY product_key, period_key{unit_group}{qualifier_group}{source_group}{partner_group}
                    ) partner_rows
                    GROUP BY product_key, period_key, unit_key, qualifier_key, source_key
                ) source_rows
                GROUP BY product_key, period_key, unit_key, qualifier_key
            """
        else:
            query = f"""
                SELECT
                    product_key,
                    unit_key,
                    qualifier_key,
                    period_key,
                    MAX(metric_value)::double precision AS metric_value
                FROM (
                    SELECT
                        COALESCE(t.product_code::text, 'N/A') AS product_key,
                        {unit_select}
                        {qualifier_select}
                        {source_select}
                        {partner_select}
                        COALESCE(t.time_period::text, 'N/A') AS period_key,
                        MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
                    FROM {fact_table} t
                    {where_sql}
                    GROUP BY product_key, period_key{unit_group}{qualifier_group}{source_group}{partner_group}
                ) source_rows
                GROUP BY product_key, period_key, unit_key, qualifier_key
            """
    else:
        query = f"""
            SELECT
                COALESCE(t.product_code::text, 'N/A') AS product_key,
                {unit_select}
                {qualifier_select}
                COALESCE(t.time_period::text, 'N/A') AS period_key,
                MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
            FROM {fact_table} t
            {where_sql}
            GROUP BY product_key, period_key{unit_group}{qualifier_group}
        """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *query_params)

    staged_values: dict[tuple[str, str], list[tuple[str, str, float]]] = defaultdict(list)
    period_from = source_template.get("period_from")
    from_key = (
        _period_sort_key(str(period_from))
        if isinstance(period_from, str) and period_from.strip()
        else None
    )
    for row in rows:
        code = str(row["product_key"])
        period_key = str(row["period_key"])
        if from_key is not None and _period_sort_key(period_key) < from_key:
            continue
        unit_key = str(row["unit_key"])
        qualifier_key = str(row["qualifier_key"])
        value = float(row["metric_value"] or 0.0)
        staged_values[(code, period_key)].append((qualifier_key, unit_key, value))
    return _finalize_guide_period_map(
        staged_values,
        prefer_qualifier=prefer_qualifier,
        qualifier_priority=qualifier_priority,
    )


def _filter_period_values_by_from(
    period_values: dict[str, float],
    period_from: str | None,
) -> dict[str, float]:
    if not isinstance(period_from, str) or not period_from.strip():
        return period_values
    from_key = _period_sort_key(period_from)
    return {
        period: value
        for period, value in period_values.items()
        if _period_sort_key(period) >= from_key
    }


async def _country_has_oecd_balance_data(country_code: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM oil.fact_oil_balance
                WHERE UPPER(country_code::text) = UPPER($1)
            )
            """,
            country_code,
        )
    return bool(exists)


async def _fetch_total_partner_aggregate_values(
    *,
    fact_table: str,
    filters: dict[str, list[str]],
    country_filter_key: str | None,
    country_code: str,
    total_partner_code: str,
    total_product_codes: list[str],
    period_from: str | None,
) -> dict[str, float]:
    if not total_product_codes:
        return {}

    query_filters = {
        key: list(values)
        for key, values in filters.items()
        if key != "product_code"
    }
    query_filters["partner_code"] = [total_partner_code]
    query_filters["product_code"] = list(total_product_codes)
    if country_code and country_filter_key:
        query_filters[country_filter_key] = [country_code]

    query_filters = _normalize_guide_filters(query_filters)
    columns_set = await get_table_columns(fact_table)
    allowed_filter_columns = {spec["key"] for spec in map_filterable_columns(columns_set)}
    where_sql, query_params = build_where_clause(
        selected_filter_values=query_filters,
        allowed_filter_columns=allowed_filter_columns,
    )
    if "source_id" in columns_set:
        query = f"""
            SELECT
                period_key,
                MAX(metric_value)::double precision AS metric_value
            FROM (
                SELECT
                    COALESCE(t.time_period::text, 'N/A') AS period_key,
                    COALESCE(t.source_id::text, 'N/A') AS source_key,
                    MAX(COALESCE(t.value::numeric, 0))::double precision AS metric_value
                FROM {fact_table} t
                {where_sql}
                GROUP BY period_key, source_key
            ) source_rows
            GROUP BY period_key
        """
    else:
        query = f"""
            SELECT
                COALESCE(t.time_period::text, 'N/A') AS period_key,
                SUM(COALESCE(t.value::numeric, 0))::double precision AS metric_value
            FROM {fact_table} t
            {where_sql}
            GROUP BY period_key
        """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *query_params)

    period_values: dict[str, float] = defaultdict(float)
    for row in rows:
        period_key = str(row["period_key"])
        period_values[period_key] += float(row["metric_value"] or 0.0)
    return _filter_period_values_by_from(dict(period_values), period_from)


async def _build_oecd_crude_production_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    start_year: int,
    current_year: int,
    current_month: int,
    latest_label_template: str,
    pct_label_template: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_templates = template.get("sources")
    if not isinstance(source_templates, list):
        return ([], [])

    annual_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "A"
        ),
        None,
    )
    monthly_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "M"
        ),
        None,
    )
    aggregate_period_values = bool(template.get("aggregate_period_values"))
    value_scale = float(template.get("value_scale", 1.0))
    round_digits = int(template["round_digits"]) if isinstance(template.get("round_digits"), int) else 1
    row_labels = dict(template.get("row_labels", {}))

    if aggregate_period_values:
        annual_aggregate = (
            await _fetch_guide_aggregate_period_values(
                source_template=annual_template,
                country_code=country_code,
                default_fact_table=default_fact_table,
                default_country_filter_key=default_country_filter_key,
            )
            if isinstance(annual_template, dict)
            else {}
        )
        monthly_aggregate = (
            await _fetch_guide_aggregate_period_values(
                source_template=monthly_template,
                country_code=country_code,
                default_fact_table=default_fact_table,
                default_country_filter_key=default_country_filter_key,
            )
            if isinstance(monthly_template, dict)
            else {}
        )
        annual_values = {"_AGG": annual_aggregate} if annual_aggregate else {}
        monthly_values = {"_AGG": monthly_aggregate} if monthly_aggregate else {}
        crude_codes = ["_AGG"]
    else:
        annual_values = (
            await _fetch_guide_source_period_values(
                source_template=annual_template,
                country_code=country_code,
                default_fact_table=default_fact_table,
                default_country_filter_key=default_country_filter_key,
            )
            if isinstance(annual_template, dict)
            else {}
        )
        monthly_values = (
            await _fetch_guide_source_period_values(
                source_template=monthly_template,
                country_code=country_code,
                default_fact_table=default_fact_table,
                default_country_filter_key=default_country_filter_key,
            )
            if isinstance(monthly_template, dict)
            else {}
        )
        row_products = dict(template.get("row_products", {}))
        crude_codes = _resolve_product_codes([str(item) for item in row_products.get("crude", ["CRUDEOIL"])])

    annual_years = _collect_guide_annual_years(annual_values)
    full_month_years = _full_month_years(monthly_values, current_year=current_year)
    max_year_candidates = {year for year in annual_years.union(full_month_years) if year >= start_year}
    if max_year_candidates:
        max_completed_year = max(max_year_candidates)
    else:
        max_completed_year = current_year - 1

    year_columns = [str(year) for year in range(start_year, max_completed_year + 1)]

    crude_label = str(row_labels.get("crude", "Сырая нефть"))
    relevant_codes = set(crude_codes)

    available_months_current_year: set[int] = set()
    for product_code, values in monthly_values.items():
        if product_code not in relevant_codes:
            continue
        for period_key in values.keys():
            month = _month_in_year(period_key, current_year)
            if month is None:
                continue
            available_months_current_year.add(month)
    latest_available_month = max(available_months_current_year) if available_months_current_year else None
    if latest_available_month is None:
        latest_period_label = "нет данных"
        pct_label = "% к нет данных"
    else:
        latest_period_label = latest_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=latest_available_month,
        )
        pct_label = pct_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=latest_available_month,
        )
    columns = ["Показатель", *year_columns, latest_period_label, pct_label]

    payload: dict[str, Any] = {"Показатель": crude_label}
    for year in year_columns:
        annual_value = _scale_guide_number(
            _sum_for_codes_at_period(annual_values, crude_codes, year),
            value_scale,
        )
        if annual_value is not None:
            payload[year] = _round_guide_number(annual_value, round_digits)
            continue
        year_int = int(year)
        if year_int in full_month_years:
            payload[year] = _round_guide_number(
                _scale_guide_number(
                    _sum_codes_for_year_months(monthly_values, crude_codes, year_int, range(1, 13)),
                    value_scale,
                ),
                round_digits,
            )
        else:
            payload[year] = None

    current_months = (
        range(1, latest_available_month + 1) if latest_available_month is not None else []
    )
    latest_value = (
        _scale_guide_number(
            _sum_codes_for_year_months(monthly_values, crude_codes, current_year, current_months),
            value_scale,
        )
        if latest_available_month is not None
        else None
    )
    previous_value = (
        _scale_guide_number(
            _sum_codes_for_year_months(monthly_values, crude_codes, current_year - 1, current_months),
            value_scale,
        )
        if latest_available_month is not None
        else None
    )
    payload[latest_period_label] = _round_guide_number(latest_value, round_digits)
    payload[pct_label] = (
        _round_guide_number((latest_value - previous_value) / previous_value * 100.0, round_digits)
        if latest_value is not None and previous_value not in (None, 0)
        else None
    )

    return (columns, [payload])


async def _build_oecd_products_consumption_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    start_year: int,
    current_year: int,
    latest_label_template: str,
    pct_label_template: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_templates = template.get("sources")
    row_definitions_raw = template.get("row_definitions")
    if not isinstance(source_templates, list) or not isinstance(row_definitions_raw, list):
        return ([], [])

    prefer_qualifier = bool(template.get("prefer_qualifier"))
    value_scale = float(template.get("value_scale", 1.0))
    round_digits = int(template["round_digits"]) if isinstance(template.get("round_digits"), int) else 1
    optional_row_labels = {
        str(label)
        for label in template.get("optional_row_labels", [])
        if str(label).strip()
    }

    def scaled_round(value: float | None) -> float | None:
        return _round_guide_number(_scale_guide_number(value, value_scale), round_digits)

    annual_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "A"
        ),
        None,
    )
    monthly_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "M"
        ),
        None,
    )
    annual_values = (
        await _fetch_guide_source_period_values(
            source_template=annual_template,
            country_code=country_code,
            default_fact_table=default_fact_table,
            default_country_filter_key=default_country_filter_key,
            prefer_qualifier=prefer_qualifier,
        )
        if isinstance(annual_template, dict)
        else {}
    )
    monthly_values = (
        await _fetch_guide_source_period_values(
            source_template=monthly_template,
            country_code=country_code,
            default_fact_table=default_fact_table,
            default_country_filter_key=default_country_filter_key,
            prefer_qualifier=prefer_qualifier,
        )
        if isinstance(monthly_template, dict)
        else {}
    )

    annual_years: set[int] = set()
    for values in annual_values.values():
        for period_key in values.keys():
            if re.fullmatch(r"\d{4}", period_key):
                annual_years.add(int(period_key))
    full_month_years = _full_month_years(monthly_values, current_year=current_year)
    max_year_candidates = {year for year in annual_years.union(full_month_years) if year >= start_year}
    if max_year_candidates:
        max_completed_year = max(max_year_candidates)
    else:
        max_completed_year = current_year - 1

    year_columns = [str(year) for year in range(start_year, max_completed_year + 1)]

    relevant_codes: set[str] = set()
    row_definitions: list[tuple[str, list[str]]] = []
    for row_definition in row_definitions_raw:
        if not isinstance(row_definition, dict):
            continue
        label = str(row_definition.get("label", "")).strip()
        products_raw = row_definition.get("products")
        if not label or not isinstance(products_raw, list):
            continue
        product_codes = _resolve_product_codes([str(item) for item in products_raw])
        if not product_codes:
            continue
        row_definitions.append((label, product_codes))
        relevant_codes.update(product_codes)

    available_months_current_year: set[int] = set()
    for product_code, values in monthly_values.items():
        if product_code not in relevant_codes:
            continue
        for period_key in values.keys():
            month = _month_in_year(period_key, current_year)
            if month is not None:
                available_months_current_year.add(month)
    latest_available_month = max(available_months_current_year) if available_months_current_year else None
    if latest_available_month is None:
        latest_period_label = "нет данных"
        pct_label = "% к нет данных"
    else:
        latest_period_label = latest_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=latest_available_month,
        )
        pct_label = pct_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=latest_available_month,
        )
    columns = ["Показатель", *year_columns, latest_period_label, pct_label]

    current_months = (
        range(1, latest_available_month + 1) if latest_available_month is not None else []
    )
    rows: list[dict[str, Any]] = []
    for row_label, product_codes in row_definitions:
        payload: dict[str, Any] = {"Показатель": row_label}
        for year in year_columns:
            annual_value = _sum_for_codes_at_period(annual_values, product_codes, year)
            if annual_value is not None:
                payload[year] = scaled_round(annual_value)
                continue
            year_int = int(year)
            if year_int in full_month_years:
                payload[year] = scaled_round(
                    _sum_codes_for_year_months(monthly_values, product_codes, year_int, range(1, 13))
                )
            else:
                payload[year] = None

        latest_value = (
            _sum_codes_for_year_months(monthly_values, product_codes, current_year, current_months)
            if latest_available_month is not None
            else None
        )
        previous_value = (
            _sum_codes_for_year_months(
                monthly_values,
                product_codes,
                current_year - 1,
                current_months,
            )
            if latest_available_month is not None
            else None
        )
        payload[latest_period_label] = scaled_round(latest_value)
        payload[pct_label] = (
            scaled_round((latest_value - previous_value) / previous_value * 100.0)
            if latest_value is not None and previous_value not in (None, 0)
            else None
        )
        if optional_row_labels and row_label in optional_row_labels:
            value_columns = [column for column in columns if column != "Показатель"]
            if all(_is_zero_like_guide_value(payload.get(column)) for column in value_columns):
                continue
        rows.append(payload)

    return (columns, rows)


async def _build_nonoecd_world_supply_annual_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    start_year: int,
    current_year: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    if bool(template.get("require_no_oecd_balance")) and await _country_has_oecd_balance_data(
        country_code
    ):
        return ([], [])

    source_templates = template.get("sources")
    row_definitions_raw = template.get("row_definitions")
    if not isinstance(source_templates, list) or not isinstance(row_definitions_raw, list):
        return ([], [])

    annual_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "A"
        ),
        None,
    )
    if not isinstance(annual_template, dict):
        return ([], [])

    prefer_qualifier = bool(template.get("prefer_qualifier"))
    qualifier_priority = _resolve_qualifier_priority(template)
    annual_values = await _fetch_guide_source_period_values(
        source_template=annual_template,
        country_code=country_code,
        default_fact_table=default_fact_table,
        default_country_filter_key=default_country_filter_key,
        prefer_qualifier=prefer_qualifier,
        qualifier_priority=qualifier_priority,
    )

    annual_years: set[int] = set()
    for values in annual_values.values():
        for period_key in values.keys():
            if re.fullmatch(r"\d{4}", period_key):
                annual_years.add(int(period_key))
    if annual_years:
        max_year = min(max(annual_years), current_year - 1)
    else:
        max_year = current_year - 2
    year_columns = [str(year) for year in range(start_year, max_year + 1)]
    columns = ["Показатель", *year_columns]

    row_definitions: list[tuple[str, list[str]]] = []
    for row_definition in row_definitions_raw:
        if not isinstance(row_definition, dict):
            continue
        label = str(row_definition.get("label", "")).strip()
        products_raw = row_definition.get("products")
        if not label or not isinstance(products_raw, list):
            continue
        product_codes = _resolve_product_codes([str(item) for item in products_raw])
        if not product_codes:
            continue
        row_definitions.append((label, product_codes))

    rows: list[dict[str, Any]] = []
    for row_label, product_codes in row_definitions:
        payload: dict[str, Any] = {"Показатель": row_label}
        for year in year_columns:
            payload[year] = _round_guide_number(
                _sum_for_codes_at_period(annual_values, product_codes, year)
            )
        rows.append(payload)

    return (columns, rows)


async def _build_oecd_products_structure_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    current_year: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_templates = template.get("sources")
    column_definitions_raw = template.get("column_definitions")
    if not isinstance(source_templates, list) or not isinstance(column_definitions_raw, list):
        return ([], [])

    monthly_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "M"
        ),
        None,
    )
    if not isinstance(monthly_template, dict):
        return ([], [])

    prefer_qualifier = bool(template.get("prefer_qualifier"))
    round_digits = int(template["round_digits"]) if isinstance(template.get("round_digits"), int) else 1
    other_label = str(template.get("other_label", "Прочие нефтепродукты"))
    total_label = str(template.get("total_label", "Всего"))
    total_products = _resolve_product_codes(
        [str(item) for item in template.get("total_products", ["TOTPRODS"])]
        if isinstance(template.get("total_products"), list)
        else ["TOTPRODS"]
    )

    column_definitions: list[tuple[str, list[str]]] = []
    for column_definition in column_definitions_raw:
        if not isinstance(column_definition, dict):
            continue
        label = str(column_definition.get("label", "")).strip()
        products_raw = column_definition.get("products")
        if not label or not isinstance(products_raw, list):
            continue
        product_codes = _resolve_product_codes([str(item) for item in products_raw])
        if not product_codes:
            continue
        column_definitions.append((label, product_codes))

    if not column_definitions or not total_products:
        return ([], [])

    monthly_values = await _fetch_guide_source_period_values(
        source_template=monthly_template,
        country_code=country_code,
        default_fact_table=default_fact_table,
        default_country_filter_key=default_country_filter_key,
        prefer_qualifier=prefer_qualifier,
    )
    if not monthly_values:
        return ([], [])

    total_period_map = {
        code: monthly_values.get(code, {})
        for code in total_products
        if code in monthly_values
    }
    full_years = _full_month_years(total_period_map, current_year=current_year)
    if not full_years:
        return ([], [])

    target_year = max(full_years)
    year_label = f"{target_year} г."
    columns = ["Показатель", year_label, "Доля в структуре"]

    named_values: dict[str, float | None] = {}
    for label, product_codes in column_definitions:
        named_values[label] = _round_guide_number(
            _sum_codes_for_year_months(monthly_values, product_codes, target_year, range(1, 13)),
            round_digits,
        )

    total_value = _round_guide_number(
        _sum_codes_for_year_months(monthly_values, total_products, target_year, range(1, 13)),
        round_digits,
    )
    if total_value in (None, 0):
        return (columns, [])

    named_sum = sum(value for value in named_values.values() if value is not None)
    other_value = _round_guide_number(float(total_value) - named_sum, round_digits)

    rows: list[dict[str, Any]] = []
    named_share_sum = 0.0
    for label, product_codes in column_definitions:
        value = named_values.get(label)
        if value is None:
            share = None
        else:
            share = _round_guide_number(float(value) / float(total_value) * 100.0, round_digits)
            if share is not None:
                named_share_sum += float(share)
        rows.append(
            {
                "Показатель": label,
                year_label: value,
                "Доля в структуре": share,
            }
        )

    other_share = _round_guide_number(100.0 - named_share_sum, round_digits)
    rows.append(
        {
            "Показатель": other_label,
            year_label: other_value,
            "Доля в структуре": other_share,
        }
    )
    rows.append(
        {
            "Показатель": total_label,
            year_label: total_value,
            "Доля в структуре": _round_guide_number(100.0, round_digits),
        }
    )

    return (columns, rows)


async def _build_nonoecd_crude_production_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    start_year: int,
    current_year: int,
    current_month: int,
    latest_label_template: str,
    pct_label_template: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_templates = template.get("sources")
    if not isinstance(source_templates, list):
        return ([], [])

    monthly_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "M"
        ),
        None,
    )
    if not isinstance(monthly_template, dict):
        return ([], [])

    monthly_values = await _fetch_guide_source_period_values(
        source_template=monthly_template,
        country_code=country_code,
        default_fact_table=default_fact_table,
        default_country_filter_key=default_country_filter_key,
    )

    row_products = dict(template.get("row_products", {}))
    crude_codes = _resolve_product_codes([str(item) for item in row_products.get("crude", ["CRUDEOIL"])])
    relevant_codes = set(crude_codes)
    row_label = str(template.get("row_label", "Сырая нефть"))
    fixed_bbl_t = float(template.get("fixed_bbl_t") or 0.0)
    if fixed_bbl_t <= 0:
        return ([], [])

    converted_monthly_values: dict[str, dict[str, float]] = defaultdict(dict)
    for product_code, values in monthly_values.items():
        if product_code not in relevant_codes:
            continue
        for period_key, metric_value in values.items():
            if _parse_month_period(period_key) is None:
                continue
            period_days = _days_in_period(period_key)
            if period_days is None:
                continue
            converted = float(metric_value) / fixed_bbl_t * period_days
            converted_monthly_values[product_code][period_key] = (
                converted_monthly_values[product_code].get(period_key, 0.0) + converted
            )

    full_month_years = _full_month_years(converted_monthly_values, current_year=current_year)
    annual_periods = [str(year) for year in range(start_year, current_year)]

    available_months_current_year: set[int] = set()
    for product_code, values in converted_monthly_values.items():
        if product_code not in relevant_codes:
            continue
        for period_key in values.keys():
            month = _month_in_year(period_key, current_year)
            if month is not None:
                available_months_current_year.add(month)
    latest_available_month = max(available_months_current_year) if available_months_current_year else None
    report_month = _guide_report_month_cap(
        current_month=current_month,
        latest_available_month=latest_available_month,
    )

    if report_month is None:
        latest_period_label = "нет данных"
        pct_label = "% к нет данных"
    else:
        latest_period_label = latest_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=report_month,
        )
        pct_label = pct_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=report_month,
        )

    columns = ["Показатель", *annual_periods, latest_period_label, pct_label]
    payload: dict[str, Any] = {"Показатель": row_label}

    for year in annual_periods:
        year_int = int(year)
        if year_int not in full_month_years:
            payload[year] = None
            continue
        payload[year] = _round_guide_number(
            _sum_codes_for_year_months(
                converted_monthly_values,
                crude_codes,
                year_int,
                range(1, 13),
            )
        )

    current_months = range(1, report_month + 1) if report_month is not None else []
    latest_value = (
        _sum_codes_for_year_months(
            converted_monthly_values,
            crude_codes,
            current_year,
            current_months,
        )
        if report_month is not None
        else None
    )
    previous_value = (
        _sum_codes_for_year_months(
            converted_monthly_values,
            crude_codes,
            current_year - 1,
            current_months,
        )
        if report_month is not None
        else None
    )

    payload[latest_period_label] = _round_guide_number(latest_value)
    payload[pct_label] = (
        _round_guide_number((latest_value - previous_value) / previous_value * 100.0)
        if latest_value is not None and previous_value not in (None, 0)
        else None
    )
    return (columns, [payload])


async def _build_oecd_field_production_tz_rows(
    *,
    template: dict[str, Any],
    country_code: str,
    default_fact_table: str,
    default_country_filter_key: str | None,
    start_year: int,
    current_year: int,
    current_month: int,
    latest_label_template: str,
    pct_label_template: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    source_templates = template.get("sources")
    if not isinstance(source_templates, list):
        return ([], [])

    annual_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "A"
        ),
        None,
    )
    monthly_template = next(
        (
            source
            for source in source_templates
            if isinstance(source, dict) and str(source.get("frequency_code")) == "M"
        ),
        None,
    )
    if not isinstance(annual_template, dict) or not isinstance(monthly_template, dict):
        return ([], [])

    async def _fetch_field_period_values(source_template: dict[str, Any]) -> dict[str, dict[str, float]]:
        fact_table = str(source_template.get("fact_table") or default_fact_table)
        source_filters = {
            key: list(values)
            for key, values in dict(source_template.get("base_filters", {})).items()
        }
        frequency_code = source_template.get("frequency_code")
        if frequency_code:
            source_filters["frequency_code"] = [str(frequency_code)]

        country_filter_key = default_country_filter_key
        if fact_table != default_fact_table:
            country_filter_key = await _resolve_country_filter_key(fact_table)
        if country_code and country_filter_key:
            source_filters[country_filter_key] = [country_code]

        source_filters = _normalize_guide_filters(source_filters)

        columns_set = await get_table_columns(fact_table)
        if "field_code" not in columns_set:
            return {}
        allowed_filter_columns = {spec["key"] for spec in map_filterable_columns(columns_set)}
        where_sql, query_params = build_where_clause(
            selected_filter_values=source_filters,
            allowed_filter_columns=allowed_filter_columns,
        )
        query = f"""
            SELECT
                COALESCE(t.field_code::text, 'N/A') AS row_key,
                COALESCE(t.product_code::text, 'N/A') AS product_key,
                COALESCE(t.time_period::text, 'N/A') AS period_key,
                SUM(COALESCE(t.value::numeric, 0))::double precision AS metric_value
            FROM {fact_table} t
            {where_sql}
            GROUP BY row_key, product_key, period_key
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *query_params)

        period_from = source_template.get("period_from")
        from_key = (
            _period_sort_key(str(period_from))
            if isinstance(period_from, str) and period_from.strip()
            else None
        )

        product_codes = {str(row["product_key"]) for row in rows}
        conversion_map, crude_by_year, latest_crude = await _load_bbl_t_conversion_map(product_codes)
        fixed_bbl_t = float(template.get("fixed_bbl_t") or 0.0)
        use_fixed_bbl_t = fixed_bbl_t > 0

        row_period_values: dict[str, dict[str, float]] = defaultdict(dict)
        for row in rows:
            row_key = str(row["row_key"])
            period_key = str(row["period_key"])
            if from_key is not None and _period_sort_key(period_key) < from_key:
                continue
            period_year = _period_year(period_key)
            period_days = _days_in_period(period_key)
            if period_year is None or period_days is None:
                continue

            metric_value = float(row["metric_value"] or 0.0)
            if use_fixed_bbl_t:
                bbl_t = fixed_bbl_t
            else:
                product_code = str(row["product_key"])
                bbl_t = _resolve_bbl_t_conversion(
                    year=int(period_year),
                    product_code=product_code,
                    conversion_map=conversion_map,
                    crude_by_year=crude_by_year,
                    latest_crude=latest_crude,
                )
            if bbl_t in (None, 0):
                continue
            converted = metric_value / float(bbl_t) * period_days
            row_period_values[row_key][period_key] = (
                row_period_values[row_key].get(period_key, 0.0) + converted
            )
        return row_period_values

    annual_values = await _fetch_field_period_values(annual_template)
    monthly_values = await _fetch_field_period_values(monthly_template)
    field_label_map = await _resolve_row_label_map(
        fact_table=default_fact_table,
        row_dimension=str(template.get("row_dimension", "field_code")),
    )

    annual_years: set[int] = set()
    for values in annual_values.values():
        for period_key in values.keys():
            if re.fullmatch(r"\d{4}", period_key):
                year = int(period_key)
                if year < current_year:
                    annual_years.add(year)
    max_completed_year = max(annual_years) if annual_years else current_year - 1
    year_columns = [str(year) for year in range(start_year, max_completed_year + 1)]

    available_months_current_year: set[int] = set()
    for values in monthly_values.values():
        for period_key in values.keys():
            month = _month_in_year(period_key, current_year)
            if month is not None:
                available_months_current_year.add(month)
    latest_available_month = max(available_months_current_year) if available_months_current_year else None
    report_month = _guide_report_month_cap(
        current_month=current_month,
        latest_available_month=latest_available_month,
    )

    if report_month is None:
        latest_period_label = "нет данных"
        pct_label = "% к нет данных"
    else:
        latest_period_label = latest_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=report_month,
        )
        pct_label = pct_label_template.format(
            year=current_year,
            prev_year=current_year - 1,
            x=report_month,
        )
    columns = ["Показатель", *year_columns, latest_period_label, pct_label]

    row_keys = sorted(set(annual_values.keys()).union(monthly_values.keys()))
    rows: list[dict[str, Any]] = []
    for row_key in row_keys:
        row_label = field_label_map.get(row_key, row_key)
        payload: dict[str, Any] = {"Показатель": row_label}

        annual_row_values = annual_values.get(row_key, {})
        monthly_row_values = monthly_values.get(row_key, {})
        full_month_years = _full_month_years({"row": monthly_row_values}, current_year=current_year)

        for year in year_columns:
            if year in annual_row_values:
                payload[year] = _round_guide_number(annual_row_values.get(year))
                continue
            year_int = int(year)
            if year_int in full_month_years:
                payload[year] = _round_guide_number(
                    _sum_monthly_values_for_year(monthly_row_values, year_int)
                )
            else:
                payload[year] = None

        current_months = range(1, report_month + 1) if report_month is not None else []
        latest_value = (
            _sum_monthly_values_for_year_months(monthly_row_values, current_year, current_months)
            if report_month is not None
            else None
        )
        has_latest = latest_value is not None
        previous_value = (
            _sum_monthly_values_for_year_months(
                monthly_row_values,
                current_year - 1,
                current_months,
            )
            if report_month is not None
            else None
        )
        has_previous = previous_value is not None

        payload[latest_period_label] = _round_guide_number(latest_value) if has_latest else None
        payload[pct_label] = (
            _round_guide_number((latest_value - previous_value) / previous_value * 100.0)
            if has_latest and has_previous and previous_value not in (None, 0)
            else None
        )
        rows.append(payload)

    return (columns, rows)


async def fetch_filter_count_map(
    fact_table: str,
    filter_key: str,
    selected_filter_values: dict[str, list[str]],
    allowed_filter_columns: set[str],
) -> dict[str, int]:
    pool = get_pool()
    where_sql, params = build_where_clause(
        selected_filter_values=selected_filter_values,
        allowed_filter_columns=allowed_filter_columns,
        skip_key=filter_key,
    )
    query = f"""
        SELECT t.{filter_key}::text AS code, COUNT(*)::int AS row_count
        FROM {fact_table} t
        {where_sql}
        GROUP BY t.{filter_key}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return {row["code"]: row["row_count"] for row in rows}


def build_pivot(
    rows: list[dict[str, Any]],
    filter_values: dict[str, list[str]],
    available_filter_keys: list[str],
    pivot_layout: str,
    value_label_maps: dict[str, dict[str, str]],
) -> dict[str, Any]:
    if not rows:
        return {"columns": [], "rows": []}

    category_keys = determine_category_keys(
        rows=rows,
        filter_values=filter_values,
        available_filter_keys=available_filter_keys,
    )
    category_labels = [FILTER_LABELS.get(key, key) for key in category_keys]
    categories_axis_label = (
        f"Категории ({' / '.join(category_labels)})" if category_labels else "Категории"
    )

    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    row_labels: set[str] = set()
    col_labels: set[str] = set()

    for row in rows:
        time_value = str(row.get("time_period", "N/A"))
        if "frequency_code" in row:
            frequency_raw = row.get("frequency_code")
            frequency_raw_text = str(frequency_raw) if frequency_raw is not None else "N/A"
            frequency_label = value_label_maps.get("frequency_code", {}).get(
                frequency_raw_text, frequency_raw_text
            )
            time_value = f"{time_value} | {frequency_label}"

        category_parts: list[str] = []
        for key in category_keys:
            raw_value = row.get(key)
            raw_value_text = str(raw_value) if raw_value is not None else "N/A"
            label_map = value_label_maps.get(key, {})
            category_parts.append(label_map.get(raw_value_text, raw_value_text))
        category_value = " | ".join(category_parts) or "ALL"
        metric = row.get("value")
        metric_value = float(metric) if metric is not None else 0.0

        if pivot_layout == "time_columns_filters_rows":
            grouped[category_value][time_value] += metric_value
            row_labels.add(category_value)
            col_labels.add(time_value)
        else:
            grouped[time_value][category_value] += metric_value
            row_labels.add(time_value)
            col_labels.add(category_value)

    sorted_rows = sorted(row_labels)
    sorted_cols = sorted(col_labels)

    pivot_rows: list[dict[str, Any]] = []
    row_key_label = (
        categories_axis_label
        if pivot_layout == "time_columns_filters_rows"
        else FILTER_LABELS.get("time_period", "Период")
    )
    for row_key in sorted_rows:
        payload = {row_key_label: row_key}
        for col_key in sorted_cols:
            payload[col_key] = grouped[row_key].get(col_key)
        pivot_rows.append(payload)

    return {"columns": [row_key_label, *sorted_cols], "rows": pivot_rows}


@router.get("/hierarchies")
async def get_hierarchies() -> dict[str, Any]:
    fact_tables = []
    for domain in ("oil", "gas", "coal", "electricity"):
        for table in TABLES_BY_DOMAIN[domain]:
            if table.table_type != "fact":
                continue
            fact_tables.append(
                {
                    "table": table.table,
                    "label": FACT_TABLE_LABELS.get(table.table, table.description),
                    "description": table.description,
                }
            )
    return {"fact_tables": fact_tables}


@router.post("/filter-options")
async def get_filter_options(payload: FilterOptionsRequest) -> dict[str, Any]:
    allowed_tables = set(list_allowed_fact_tables())
    fact_table = payload.fact_table
    if fact_table not in allowed_tables:
        return {"fact_table": fact_table, "filters": []}

    columns = await get_table_columns(fact_table)
    filter_specs = map_filterable_columns(columns)
    allowed_filter_columns = {spec["key"] for spec in filter_specs}

    filters: list[dict[str, Any]] = []
    for spec in filter_specs:
        key = spec["key"]
        label = spec["label"]
        nodes = await fetch_filter_nodes(fact_table=fact_table, key=key)

        counts = await fetch_filter_count_map(
            fact_table=fact_table,
            filter_key=key,
            selected_filter_values=payload.selected_filter_values,
            allowed_filter_columns=allowed_filter_columns,
        )
        nodes_with_count = [
            {**node, "row_count": counts.get(str(node["code"]), 0)}
            for node in nodes
        ]
        filters.append({"key": key, "label": label, "nodes": nodes_with_count})

    return {"fact_table": fact_table, "filters": filters}


@router.get("/guide/templates")
async def get_guide_templates(domain: str | None = None) -> dict[str, Any]:
    templates = [
        {
            "id": template_id,
            "domain": template["domain"],
            "title": template["title"],
        }
        for template_id, template in GUIDE_TABLE_TEMPLATES.items()
        if domain is None or template["domain"] == domain
    ]
    return {"templates": templates}


@router.post("/guide/table")
async def build_guide_table(payload: GuideTableRequest) -> dict[str, Any]:
    template = GUIDE_TABLE_TEMPLATES.get(payload.table_id)
    if template is None:
        return {"table_id": payload.table_id, "title": "", "columns": [], "rows": []}

    fact_table = str(template["fact_table"])
    row_dimension_raw = template.get("row_dimension")
    mode = str(template.get("mode", "annual_series"))
    convert_bpd_to_kty = bool(template.get("convert_bpd_to_kty"))
    annualize_partial_year = bool(template.get("annualize_partial_year"))
    filters = {
        key: list(values)
        for key, values in dict(template.get("base_filters", {})).items()
    }
    if template.get("frequency_code"):
        filters["frequency_code"] = [str(template["frequency_code"])]

    period_from = template.get("period_from")
    current_year = datetime.now().year
    current_month = datetime.now().month
    start_year = int(period_from) if isinstance(period_from, str) and period_from.isdigit() else current_year - 6
    latest_label_template = str(template.get("latest_period_label", "мес.-4 {year}"))
    pct_label_template = str(template.get("pct_label", "% к мес.-4 {prev_year}"))
    latest_period_label = latest_label_template.format(
        year=current_year,
        prev_year=current_year - 1,
        x=current_month,
    )
    pct_label = pct_label_template.format(
        year=current_year,
        prev_year=current_year - 1,
        x=current_month,
    )

    country_filter_key = await _resolve_country_filter_key(fact_table)
    if payload.country_code and country_filter_key:
        required_scope = template.get("country_scope")
        if required_scope in {"oecd", "non_oecd"}:
            if not await _country_matches_required_scope(payload.country_code, str(required_scope)):
                columns = _build_empty_guide_columns(
                    mode=mode,
                    start_year=start_year,
                    current_year=current_year,
                    latest_period_label=latest_period_label,
                    pct_label=pct_label,
                )
                return {
                    "table_id": payload.table_id,
                    "title": template["title"],
                    "columns": columns,
                    "rows": [],
                }
        filters[country_filter_key] = [payload.country_code]

    filters = _normalize_guide_filters(filters)

    if mode == "tz_oecd_crude_production":
        columns, table_rows = await _build_oecd_crude_production_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            start_year=start_year,
            current_year=current_year,
            current_month=current_month,
            latest_label_template=latest_label_template,
            pct_label_template=pct_label_template,
        )
        table_rows = _filter_zero_rows_for_production_tables(
            title=str(template["title"]),
            columns=columns,
            rows=table_rows,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    if mode == "tz_oecd_products_consumption":
        columns, table_rows = await _build_oecd_products_consumption_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            start_year=start_year,
            current_year=current_year,
            latest_label_template=latest_label_template,
            pct_label_template=pct_label_template,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    if mode == "tz_oecd_products_structure":
        columns, table_rows = await _build_oecd_products_structure_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            current_year=current_year,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    if mode == "tz_nonoecd_world_supply_annual":
        columns, table_rows = await _build_nonoecd_world_supply_annual_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            start_year=start_year,
            current_year=current_year,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    if mode == "tz_nonoecd_crude_production":
        columns, table_rows = await _build_nonoecd_crude_production_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            start_year=start_year,
            current_year=current_year,
            current_month=current_month,
            latest_label_template=latest_label_template,
            pct_label_template=pct_label_template,
        )
        table_rows = _filter_zero_rows_for_production_tables(
            title=str(template["title"]),
            columns=columns,
            rows=table_rows,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    if mode == "tz_oecd_field_production":
        columns, table_rows = await _build_oecd_field_production_tz_rows(
            template=template,
            country_code=payload.country_code,
            default_fact_table=fact_table,
            default_country_filter_key=country_filter_key,
            start_year=start_year,
            current_year=current_year,
            current_month=current_month,
            latest_label_template=latest_label_template,
            pct_label_template=pct_label_template,
        )
        table_rows = _filter_zero_rows_for_production_tables(
            title=str(template["title"]),
            columns=columns,
            rows=table_rows,
        )
        return {
            "table_id": payload.table_id,
            "title": template["title"],
            "columns": columns,
            "rows": table_rows,
        }

    columns_set = await get_table_columns(fact_table)
    product_group = GUIDE_TEMPLATE_PRODUCT_GROUP.get(payload.table_id)
    template_product_codes = template.get("base_filters", {}).get("product_code")
    if (
        "product_code" in columns_set
        and product_group in OIL_PRODUCT_WHITELISTS
        and not template_product_codes
    ):
        filters["product_code"] = _resolve_product_codes(list(OIL_PRODUCT_WHITELISTS[product_group]))
    filters = _normalize_guide_filters(filters)
    allowed_filter_columns = {spec["key"] for spec in map_filterable_columns(columns_set)}
    where_sql, query_params = build_where_clause(
        selected_filter_values=filters,
        allowed_filter_columns=allowed_filter_columns,
    )

    if isinstance(row_dimension_raw, str):
        row_dimension_candidates = [row_dimension_raw]
    elif isinstance(row_dimension_raw, list):
        row_dimension_candidates = [str(item) for item in row_dimension_raw if isinstance(item, str)]
    else:
        row_dimension_candidates = []
    row_dimension = next((candidate for candidate in row_dimension_candidates if candidate in columns_set), None)
    apply_bpd_conversion = convert_bpd_to_kty and "product_code" in columns_set

    if row_dimension:
        select_dimension = f"COALESCE(t.{row_dimension}::text, 'N/A') AS row_key"
        group_dimension = "row_key"
    else:
        select_dimension = "'Итого'::text AS row_key"
        group_dimension = "row_key"
    select_product = "COALESCE(t.product_code::text, 'N/A') AS product_key" if apply_bpd_conversion else "'N/A'::text AS product_key"
    group_product = ", product_key" if apply_bpd_conversion else ""

    pool = get_pool()
    query = f"""
        SELECT
            {select_dimension},
            {select_product},
            COALESCE(t.time_period::text, 'N/A') AS period_key,
            SUM(COALESCE(t.value::numeric, 0))::double precision AS metric_value
        FROM {fact_table} t
        {where_sql}
        GROUP BY {group_dimension}{group_product}, period_key
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *query_params)

    label_map = await _resolve_row_label_map(fact_table=fact_table, row_dimension=row_dimension)
    total_partner_code = (
        str(template["annual_share_total_partner"])
        if template.get("annual_share_total_partner")
        else None
    )
    total_partner_label = (
        label_map.get(total_partner_code, total_partner_code)
        if total_partner_code
        else None
    )
    total_product_codes: list[str] | None = None
    total_product_raw = template.get("annual_share_total_product")
    if isinstance(total_product_raw, str) and total_product_raw.strip():
        total_product_codes = _resolve_product_codes([total_product_raw])
    elif isinstance(total_product_raw, list):
        total_product_codes = _resolve_product_codes([str(item) for item in total_product_raw if str(item).strip()])
    non_aggregate_country_codes: set[str] | None = None
    if mode == "annual_share" and isinstance(template.get("top_n_rows"), int):
        non_aggregate_country_codes = await _resolve_non_aggregate_country_codes(
            fact_table=fact_table,
            row_dimension=row_dimension,
        )
    conversion_map: dict[tuple[int, str], float] = {}
    crude_by_year: dict[int, float] = {}
    latest_crude: float | None = None
    if apply_bpd_conversion:
        product_codes = {str(row["product_key"]) for row in rows}
        conversion_map, crude_by_year, latest_crude = await _load_bbl_t_conversion_map(product_codes)

    row_period_values: dict[str, dict[str, float]] = defaultdict(dict)
    total_partner_period_values: dict[str, float] = defaultdict(float)
    for row in rows:
        raw_row_key = str(row["row_key"])
        if total_partner_code and raw_row_key == total_partner_code:
            if total_product_codes:
                continue
            period_key = str(row["period_key"])
            metric_value = float(row["metric_value"] or 0.0)
            total_partner_period_values[period_key] += metric_value
            continue
        if non_aggregate_country_codes is not None and raw_row_key not in non_aggregate_country_codes:
            continue
        row_label = label_map.get(raw_row_key, raw_row_key)
        period_key = str(row["period_key"])
        metric_value = float(row["metric_value"] or 0.0)
        if apply_bpd_conversion:
            period_year = _period_year(period_key)
            period_days = _days_in_period(period_key)
            if period_year is None or period_days is None:
                continue
            product_code = str(row["product_key"])
            bbl_t = _resolve_bbl_t_conversion(
                year=int(period_year),
                product_code=product_code,
                conversion_map=conversion_map,
                crude_by_year=crude_by_year,
                latest_crude=latest_crude,
            )
            if bbl_t in (None, 0):
                continue
            metric_value = metric_value / bbl_t * period_days
        row_period_values[row_label][period_key] = row_period_values[row_label].get(period_key, 0.0) + metric_value

    if total_partner_code and total_product_codes:
        total_partner_period_values = await _fetch_total_partner_aggregate_values(
            fact_table=fact_table,
            filters=filters,
            country_filter_key=country_filter_key,
            country_code=payload.country_code,
            total_partner_code=total_partner_code,
            total_product_codes=total_product_codes,
            period_from=str(period_from) if isinstance(period_from, str) else None,
        )
    elif total_partner_period_values:
        total_partner_period_values = _filter_period_values_by_from(
            dict(total_partner_period_values),
            str(period_from) if isinstance(period_from, str) else None,
        )

    if isinstance(period_from, str) and period_from:
        from_key = _period_sort_key(period_from)
        filtered_values: dict[str, dict[str, float]] = {}
        for row_label, values in row_period_values.items():
            next_values = {
                period: value
                for period, value in values.items()
                if _period_sort_key(period) >= from_key
            }
            if next_values:
                filtered_values[row_label] = next_values
        row_period_values = filtered_values

    row_labels = sorted(row_period_values.keys(), key=lambda item: item.lower())
    value_scale = float(template.get("value_scale", 1.0))
    round_digits = int(template["round_digits"]) if isinstance(template.get("round_digits"), int) else None
    if value_scale != 1.0 or round_digits is not None:
        scaled_values: dict[str, dict[str, float]] = {}
        for row_label, values in row_period_values.items():
            scaled_values[row_label] = {
                period: _scale_guide_number(value, value_scale) or 0.0
                for period, value in values.items()
            }
        row_period_values = scaled_values
        if total_partner_period_values:
            total_partner_period_values = {
                period: _scale_guide_number(value, value_scale) or 0.0
                for period, value in total_partner_period_values.items()
            }
    if mode == "monthly_with_yoy":
        columns, table_rows = _build_monthly_with_yoy_rows(
            row_period_values=row_period_values,
            row_labels=row_labels,
            start_year=start_year,
            latest_period_label=latest_period_label,
            pct_label=pct_label,
            annualize_partial_year=annualize_partial_year,
        )
    elif mode == "annual_share":
        target_year = current_year - 2
        if str(template.get("annual_share_target", "")).lower() == "latest_available":
            available_years = sorted(
                {
                    int(period_year)
                    for values in row_period_values.values()
                    for period_key in values.keys()
                    for period_year in [_period_year(period_key)]
                    if period_year and period_year.isdigit()
                }
            )
            if available_years:
                target_year = available_years[-1]
        year_label_template = str(template.get("annual_share_year_label", "Год-2"))
        annual_share_year_label = year_label_template.format(year=target_year)
        round_digits = (
            int(template["round_digits"])
            if isinstance(template.get("round_digits"), int)
            else None
        )
        columns, table_rows = _build_annual_share_rows(
            row_period_values=row_period_values,
            row_labels=row_labels,
            target_year=target_year,
            top_n_rows=(
                int(template["top_n_rows"])
                if isinstance(template.get("top_n_rows"), int) and int(template["top_n_rows"]) > 0
                else None
            ),
            drop_empty_top_rows=bool(template.get("drop_empty_top_rows")),
            year_label=annual_share_year_label,
            round_digits=round_digits,
            total_partner_label=total_partner_label,
            total_partner_period_values=(
                dict(total_partner_period_values) if total_partner_period_values else None
            ),
        )
    else:
        columns, table_rows = _build_annual_series_rows(
            row_period_values=row_period_values,
            row_labels=row_labels,
            start_year=start_year,
            end_year=current_year - 2,
        )
        if round_digits is not None:
            for row in table_rows:
                for column in columns:
                    if column == "Показатель":
                        continue
                    row[column] = _round_guide_number(row.get(column), round_digits)

    table_rows = _filter_zero_rows_for_production_tables(
        title=str(template["title"]),
        columns=columns,
        rows=table_rows,
    )

    return {
        "table_id": payload.table_id,
        "title": template["title"],
        "columns": columns,
        "rows": table_rows,
    }


@router.post("/report")
async def build_report(filters: MasterReportFilters) -> dict[str, Any]:
    pool = get_pool()
    allowed_fact_tables = set(list_allowed_fact_tables())
    if filters.fact_table not in allowed_fact_tables:
        return {"count": 0, "columns": [], "rows": [], "pivot": {"columns": [], "rows": []}}

    column_set = await get_table_columns(filters.fact_table)
    filter_specs = map_filterable_columns(column_set)
    available_filter_keys = [spec["key"] for spec in filter_specs]
    allowed_filter_columns = set(available_filter_keys)
    where_sql, filter_params = build_where_clause(
        selected_filter_values=filters.filter_values,
        allowed_filter_columns=allowed_filter_columns,
    )
    # Для сводной таблицы используем полный набор строк без LIMIT,
    # иначе можно "потерять" часть выбранных стран/категорий.
    all_rows_query = f"""
        SELECT t.*
        FROM {filters.fact_table} t
        {where_sql}
    """

    limit_placeholder = f"${len(filter_params) + 1}"
    limited_rows_query = f"""
        SELECT t.*
        FROM {filters.fact_table} t
        {where_sql}
        ORDER BY t.created_at DESC NULLS LAST
        LIMIT {limit_placeholder};
    """
    async with pool.acquire() as conn:
        all_rows = await conn.fetch(all_rows_query, *filter_params)
        limited_rows = await conn.fetch(limited_rows_query, *filter_params, filters.limit)

    raw_records_all = [dict(row) for row in all_rows]
    raw_records_limited = [dict(row) for row in limited_rows]

    category_keys = determine_category_keys(
        rows=raw_records_all,
        filter_values=filters.filter_values,
        available_filter_keys=available_filter_keys,
    )
    map_keys = list(category_keys)
    if raw_records_all and "frequency_code" in raw_records_all[0] and "frequency_code" not in map_keys:
        map_keys.append("frequency_code")
    value_label_maps: dict[str, dict[str, str]] = {}
    for key in map_keys:
        nodes = await fetch_filter_nodes(fact_table=filters.fact_table, key=key)
        value_label_maps[key] = build_value_label_map(nodes)

    clean_records: list[dict[str, Any]] = []
    for row in raw_records_limited:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            if key in TECHNICAL_COLUMNS:
                continue
            clean_row[FILTER_LABELS.get(key, key)] = value
        clean_records.append(clean_row)

    columns = list(clean_records[0].keys()) if clean_records else []
    pivot_payload = build_pivot(
        rows=raw_records_all,
        filter_values=filters.filter_values,
        available_filter_keys=available_filter_keys,
        pivot_layout=filters.pivot_layout,
        value_label_maps=value_label_maps,
    )
    return {
        "count": len(raw_records_all),
        "columns": columns,
        "rows": clean_records,
        "pivot": pivot_payload,
    }
