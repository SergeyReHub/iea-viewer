from __future__ import annotations

from typing import Any

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
    "TOTCONS": "GRDEL_INLAND_OBS",
}


def _map_product_code(fact_table: str, code: str) -> str:
    if fact_table.startswith("oil."):
        return LEGACY_OIL_PRODUCT_CODES.get(code, code)
    return code


def _map_filter_values(fact_table: str, filters: dict[str, Any]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, values in filters.items():
        if not isinstance(values, list):
            normalized[str(key)] = []
            continue
        if key == "product_code":
            normalized[key] = [_map_product_code(fact_table, str(value)) for value in values]
        elif key == "flow_code":
            normalized[key] = [LEGACY_FLOW_CODES.get(str(value), str(value)) for value in values]
        elif key == "source_id":
            normalized[key] = [LEGACY_SOURCE_IDS.get(str(value), str(value)) for value in values]
        else:
            normalized[key] = [str(value) for value in values]
    return normalized


def adapt_v1_preset(preset: dict[str, Any]) -> dict[str, Any]:
    fact_table = str(preset.get("factTable", ""))
    selected_filter_values = preset.get("selectedFilterValues")
    if not isinstance(selected_filter_values, dict):
        selected_filter_values = {}

    pivot_layout = str(preset.get("pivotLayout", "time_rows_filters_columns"))
    if pivot_layout != "time_columns_filters_rows":
        pivot_layout = "time_rows_filters_columns"

    return {
        "id": str(preset.get("id", "")),
        "name": str(preset.get("name", "")),
        "description": str(preset.get("description", "")),
        "factTable": fact_table,
        "selectedFilterValues": _map_filter_values(fact_table, selected_filter_values),
        "pivotLayout": pivot_layout,
        "periodFrom": str(preset.get("periodFrom", "")),
        "periodTo": str(preset.get("periodTo", "")),
        "periodSort": "desc" if str(preset.get("periodSort")) == "desc" else "asc",
        "updatedAt": str(preset.get("updatedAt", "")),
        "version": int(preset.get("version") or 1),
    }
