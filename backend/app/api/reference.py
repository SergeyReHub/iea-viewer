from typing import Literal

from fastapi import APIRouter, HTTPException

from app.db.connection import fetch_all_rows
from app.metadata.tables import get_table_meta, normalize_table_name, resolve_db_table_name

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/{domain}/{table_name:path}")
async def get_reference_rows(
    domain: Literal["base", "oil", "gas", "coal", "electricity"],
    table_name: str,
) -> dict[str, object]:
    normalized_table_name = normalize_table_name(domain, table_name)
    table_meta = get_table_meta(domain, table_name)
    if table_meta is None or table_meta.table_type not in {"ref", "map"}:
        raise HTTPException(
            status_code=400,
            detail="Only ref_* and map_* tables from selected domain are allowed",
        )

    db_table_name = resolve_db_table_name(domain, table_meta.table)

    rows = await fetch_all_rows(db_table_name)
    columns = list(rows[0].keys()) if rows else []
    return {
        "domain": domain,
        "table": normalized_table_name,
        "count": len(rows),
        "columns": columns,
        "rows": rows,
    }
