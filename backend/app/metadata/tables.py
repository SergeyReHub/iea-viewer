from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


TableType = Literal["ref", "fact", "map"]
DomainName = Literal["base", "oil", "gas", "coal", "electricity"]


@dataclass(frozen=True)
class TableMeta:
    table: str
    table_type: TableType
    description: str
    doc_file: str


TABLES_BY_DOMAIN: Dict[DomainName, List[TableMeta]] = {
    "base": [
        TableMeta(
            "ref_country",
            "ref",
            "Справочник стран и региональных агрегатов.",
            "base/ref_country.md",
        ),
        TableMeta(
            "ref_unit",
            "ref",
            "Справочник единиц измерения и коэффициентов конверсии.",
            "base/ref_unit.md",
        ),
        TableMeta(
            "ref_frequency",
            "ref",
            "Справочник частоты данных (A, Q, M, W, D).",
            "base/ref_frequency.md",
        ),
        TableMeta(
            "ref_data_source",
            "ref",
            "Справочник источников данных по доменам.",
            "base/ref_data_source.md",
        ),
        TableMeta(
            "ref_energy_flow",
            "ref",
            "Справочник потоков энергетического баланса.",
            "base/ref_energy_flow.md",
        ),
        TableMeta(
            "ref_transformation_process",
            "ref",
            "Справочник процессов трансформации энергии.",
            "base/ref_transformation_process.md",
        ),
        TableMeta(
            "ref_sector",
            "ref",
            "Справочник секторов потребления (ISIC).",
            "base/ref_sector.md",
        ),
        TableMeta(
            "ref_reporting_type",
            "ref",
            "Справочник типов отчетности.",
            "base/ref_reporting_type.md",
        ),
    ],
    "oil": [
        TableMeta(
            "oil.ref_oil_product",
            "ref",
            "Справочник нефтяных продуктов.",
            "oil/ref_oil_product.md",
        ),
        TableMeta(
            "oil.ref_oil_product_alias",
            "ref",
            "Маппинг исторических и альтернативных кодов продуктов.",
            "oil/ref_oil_product_alias.md",
        ),
        TableMeta(
            "oil.ref_oil_field",
            "ref",
            "Справочник нефтяных месторождений.",
            "oil/ref_oil_field.md",
        ),
        TableMeta(
            "oil.fact_oil_crude_supply",
            "fact",
            "Факт-таблица предложения сырой нефти.",
            "oil/fact_oil_crude_supply.md",
        ),
        TableMeta(
            "oil.fact_oil_balance",
            "fact",
            "Факт-таблица баланса нефтепродуктов.",
            "oil/fact_oil_balance.md",
        ),
        TableMeta(
            "oil.fact_oil_trade",
            "fact",
            "Факт-таблица торговли (импорт/экспорт) с партнерами.",
            "oil/fact_oil_trade.md",
        ),
        TableMeta(
            "oil.fact_oil_world_supply",
            "fact",
            "Факт-таблица мирового предложения нефти.",
            "oil/fact_oil_world_supply.md",
        ),
        TableMeta(
            "oil.fact_oil_conversion",
            "fact",
            "Факт-таблица коэффициентов пересчета тонн в баррели.",
            "oil/fact_oil_conversion.md",
        ),
        TableMeta(
            "oil.fact_oil_stocks",
            "fact",
            "Факт-таблица запасов нефти и нефтепродуктов.",
            "oil/fact_oil_stocks.md",
        ),
        TableMeta(
            "oil.fact_oil_field_production",
            "fact",
            "Факт-таблица добычи по месторождениям.",
            "oil/fact_oil_field_production.md",
        ),
        TableMeta(
            "oil.fact_oil_refinery_throughput",
            "fact",
            "Факт-таблица переработки НПЗ по регионам.",
            "oil/fact_oil_refinery_throughput.md",
        ),
    ],
    "gas": [
        TableMeta(
            "gas.ref_gas_product",
            "ref",
            "Справочник газовых продуктов.",
            "gas/ref_gas_product.md",
        ),
        TableMeta(
            "gas.fact_gas_balance",
            "fact",
            "Факт-таблица баланса природного газа.",
            "gas/fact_gas_balance.md",
        ),
        TableMeta(
            "gas.fact_gas_trade",
            "fact",
            "Факт-таблица торговли газом по партнерам.",
            "gas/fact_gas_trade.md",
        ),
    ],
    "coal": [
        TableMeta(
            "coal.ref_coal_product",
            "ref",
            "Справочник угольных продуктов.",
            "coal/ref_coal_product.md",
        ),
        TableMeta(
            "coal.ref_coal_ncv_flow",
            "ref",
            "Справочник NCV-потоков угля.",
            "coal/ref_coal_ncv_flow.md",
        ),
        TableMeta(
            "coal.fact_coal_balance",
            "fact",
            "Факт-таблица баланса угля.",
            "coal/fact_coal_balance.md",
        ),
        TableMeta(
            "coal.fact_coal_ncv",
            "fact",
            "Факт-таблица NCV по углю.",
            "coal/fact_coal_ncv.md",
        ),
        TableMeta(
            "coal.fact_coal_quarterly",
            "fact",
            "Факт-таблица квартальной статистики угля.",
            "coal/fact_coal_quarterly.md",
        ),
        TableMeta(
            "coal.fact_coal_trade",
            "fact",
            "Факт-таблица торговли углем по партнерам.",
            "coal/fact_coal_trade.md",
        ),
    ],
    "electricity": [
        TableMeta(
            "electricity.ref_electricity_product",
            "ref",
            "Справочник продуктов электроэнергетики.",
            "electricity/ref_electricity_product.md",
        ),
        TableMeta(
            "electricity.ref_electricity_plant_type",
            "ref",
            "Справочник типов электростанций.",
            "electricity/ref_electricity_plant_type.md",
        ),
        TableMeta(
            "electricity.ref_electricity_indicator",
            "ref",
            "Справочник индикаторов электроэнергетики.",
            "electricity/ref_electricity_indicator.md",
        ),
        TableMeta(
            "electricity.fact_electricity_balance",
            "fact",
            "Факт-таблица баланса электроэнергии и тепла.",
            "electricity/fact_electricity_balance.md",
        ),
        TableMeta(
            "electricity.fact_electricity_trade",
            "fact",
            "Факт-таблица импорта/экспорта электроэнергии по партнерам.",
            "electricity/fact_electricity_trade.md",
        ),
        TableMeta(
            "electricity.fact_electricity_generation",
            "fact",
            "Факт-таблица генерации электроэнергии по типам станций и индикаторам.",
            "electricity/fact_electricity_generation.md",
        ),
        TableMeta(
            "electricity.fact_electricity_auto",
            "fact",
            "Факт-таблица автогенерации электроэнергии.",
            "electricity/fact_electricity_auto.md",
        ),
        TableMeta(
            "electricity.fact_electricity_capacity",
            "fact",
            "Факт-таблица установленной мощности электростанций.",
            "electricity/fact_electricity_capacity.md",
        ),
    ],
}

MAP_TABLES_BY_DOMAIN: Dict[DomainName, List[TableMeta]] = {
    "base": [
        TableMeta(
            "base.map_country_old_code",
            "map",
            "Маппинг старых кодов стран (Beyond 2020 → .Stat 2025).",
            "base/map_country_old_code.md",
        ),
        TableMeta(
            "base.map_unit_old_code",
            "map",
            "Маппинг старых кодов единиц измерения.",
            "base/map_unit_old_code.md",
        ),
        TableMeta(
            "base.map_flow_old_code",
            "map",
            "Маппинг старых кодов потоков энергобаланса.",
            "base/map_flow_old_code.md",
        ),
    ],
    "oil": [
        TableMeta(
            "oil.map_oil_product_old_code",
            "map",
            "Маппинг старых кодов нефтяных продуктов.",
            "oil/map_oil_product_old_code.md",
        ),
    ],
    "gas": [
        TableMeta(
            "gas.map_gas_product_old_code",
            "map",
            "Маппинг старых кодов газовых продуктов.",
            "gas/map_gas_product_old_code.md",
        ),
    ],
    "coal": [
        TableMeta(
            "coal.map_coal_product_old_code",
            "map",
            "Маппинг старых кодов угольных продуктов.",
            "coal/map_coal_product_old_code.md",
        ),
    ],
    "electricity": [
        TableMeta(
            "electricity.map_electricity_product_old_code",
            "map",
            "Маппинг старых кодов продуктов электроэнергетики.",
            "electricity/map_electricity_product_old_code.md",
        ),
    ],
}

ALLOWED_DOMAINS: List[DomainName] = ["base", "oil", "gas", "coal", "electricity"]


def normalize_table_name(domain: DomainName, table_name: str) -> str:
    if domain in {"oil", "gas", "coal", "electricity"} and "." not in table_name:
        return f"{domain}.{table_name}"
    return table_name


def resolve_db_table_name(domain: DomainName, table: str) -> str:
    if "." in table:
        return table
    if domain == "base":
        return f"base.{table}"
    return f"{domain}.{table}"


def get_table_meta(domain: DomainName, table_name: str) -> Optional[TableMeta]:
    normalized = normalize_table_name(domain, table_name)
    for table in TABLES_BY_DOMAIN[domain]:
        if table.table == normalized:
            return table
    for table in MAP_TABLES_BY_DOMAIN.get(domain, []):
        if table.table == normalized:
            return table
    return None
