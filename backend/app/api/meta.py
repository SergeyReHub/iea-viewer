from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.metadata.descriptions import load_table_markdown
from app.metadata.tables import ALLOWED_DOMAINS, MAP_TABLES_BY_DOMAIN, TABLES_BY_DOMAIN, get_table_meta

router = APIRouter(prefix="/meta", tags=["meta"])

TABLE_DISPLAY_NAMES: dict[str, str] = {
    "ref_country": "Страны и регионы",
    "ref_unit": "Единицы измерения",
    "ref_frequency": "Периодичность данных",
    "ref_data_source": "Источники данных",
    "ref_energy_flow": "Потоки энергетического баланса",
    "ref_transformation_process": "Процессы трансформации энергии",
    "ref_sector": "Секторы потребления",
    "ref_reporting_type": "Типы отчетности",
    "oil.ref_oil_product": "Нефтяные продукты",
    "oil.ref_oil_product_alias": "Соответствие кодов нефтепродуктов",
    "oil.ref_oil_field": "Нефтяные месторождения",
    "gas.ref_gas_product": "Газовые продукты",
    "coal.ref_coal_product": "Угольные продукты",
    "coal.ref_coal_ncv_flow": "NCV-потоки угля",
    "electricity.ref_electricity_product": "Продукты электроэнергетики",
    "electricity.ref_electricity_plant_type": "Типы электростанций",
    "electricity.ref_electricity_indicator": "Индикаторы электроэнергетики",
    "oil.fact_oil_crude_supply": "Предложение сырой нефти",
    "oil.fact_oil_balance": "Баланс нефтепродуктов",
    "oil.fact_oil_trade": "Торговля нефтью по партнерам",
    "oil.fact_oil_world_supply": "Мировое предложение нефти",
    "oil.fact_oil_conversion": "Коэффициенты пересчета (барр./тонна)",
    "oil.fact_oil_stocks": "Запасы нефти и нефтепродуктов",
    "oil.fact_oil_field_production": "Добыча по месторождениям",
    "oil.fact_oil_refinery_throughput": "Переработка на НПЗ",
    "gas.fact_gas_balance": "Баланс природного газа",
    "gas.fact_gas_trade": "Торговля газом по партнерам",
    "coal.fact_coal_balance": "Баланс угля",
    "coal.fact_coal_ncv": "NCV угля",
    "coal.fact_coal_quarterly": "Квартальная статистика угля",
    "coal.fact_coal_trade": "Торговля углем по партнерам",
    "electricity.fact_electricity_balance": "Баланс электроэнергии и тепла",
    "electricity.fact_electricity_trade": "Импорт/экспорт электроэнергии по партнерам",
    "electricity.fact_electricity_generation": "Генерация электроэнергии по типам станций",
    "electricity.fact_electricity_auto": "Автогенерация электроэнергии",
    "electricity.fact_electricity_capacity": "Установленная мощность электростанций",
    "base.map_country_old_code": "Маппинг кодов стран (legacy)",
    "base.map_unit_old_code": "Маппинг кодов единиц (legacy)",
    "base.map_flow_old_code": "Маппинг кодов потоков (legacy)",
    "oil.map_oil_product_old_code": "Маппинг кодов нефтепродуктов (legacy)",
    "gas.map_gas_product_old_code": "Маппинг кодов газовых продуктов (legacy)",
    "coal.map_coal_product_old_code": "Маппинг кодов угольных продуктов (legacy)",
    "electricity.map_electricity_product_old_code": "Маппинг кодов электроэнергетики (legacy)",
}


@router.get("/domains")
async def get_domains() -> dict[str, list[str]]:
    return {"domains": ALLOWED_DOMAINS}


@router.get("/tables")
async def get_tables(
    domain: Literal["base", "oil", "gas", "coal", "electricity"] = Query(...),
    type: Literal["ref", "fact", "map"] | None = Query(default=None),
) -> dict[str, object]:
    if domain not in TABLES_BY_DOMAIN:
        raise HTTPException(status_code=400, detail="Unsupported domain")

    tables = list(TABLES_BY_DOMAIN[domain])
    tables.extend(MAP_TABLES_BY_DOMAIN.get(domain, []))
    if type is not None:
        tables = [table for table in tables if table.table_type == type]

    payload = [
        {
            "table": table.table,
            "display_name": TABLE_DISPLAY_NAMES.get(table.table, table.table),
            "type": table.table_type,
            "description": table.description,
        }
        for table in tables
    ]
    return {"domain": domain, "count": len(payload), "tables": payload}


@router.get("/table-doc")
async def get_table_doc(
    domain: Literal["base", "oil", "gas", "coal", "electricity"] = Query(...),
    table: str = Query(...),
) -> dict[str, str]:
    table_meta = get_table_meta(domain, table)
    if table_meta is None:
        raise HTTPException(status_code=404, detail="Table is not registered for this domain")

    markdown = load_table_markdown(table_meta.doc_file)
    return {
        "domain": domain,
        "table": table_meta.table,
        "type": table_meta.table_type,
        "markdown": markdown,
    }
