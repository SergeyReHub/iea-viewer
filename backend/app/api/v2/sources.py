from fastapi import APIRouter, Depends

from app.api.deps import resolve_source, source_db_context
from app.sources.adapters.iea_etl import IeaEtlAdapter
from app.sources.pool_manager import get_pool_manager
from app.sources.registry import SourceProfile, get_registry

router = APIRouter(prefix="/v2/sources", tags=["sources"])


@router.get("")
async def list_sources() -> dict[str, object]:
    registry = get_registry()
    pool_manager = get_pool_manager()
    items = []
    for profile in registry.list_profiles():
        health = await pool_manager.health_check(profile.id)
        data_as_of_period: str | None = None
        if profile.status == "active" and health.get("db_ok") and profile.adapter == "iea_etl":
            try:
                pool = await pool_manager.get_pool(profile.id)
                adapter = IeaEtlAdapter()
                data_as_of_period = await adapter.get_data_as_of_period(pool)
            except Exception:
                data_as_of_period = None
        items.append(
            {
                "id": profile.id,
                "name": profile.name,
                "status": profile.status,
                "adapter": profile.adapter,
                "homepage_url": profile.homepage_url,
                "description": profile.description,
                "schema_version": profile.schema_version,
                "domains": list(profile.domains),
                "db_ok": health.get("db_ok", False),
                "data_as_of_period": data_as_of_period,
            }
        )
    return {"count": len(items), "sources": items}


@router.get("/{source_id}")
async def get_source(source_id: str) -> dict[str, object]:
    profile = resolve_source(source_id)
    pool_manager = get_pool_manager()
    health = await pool_manager.health_check(source_id)
    return {
        "id": profile.id,
        "name": profile.name,
        "status": profile.status,
        "adapter": profile.adapter,
        "homepage_url": profile.homepage_url,
        "description": profile.description,
        "schema_version": profile.schema_version,
        "domains": list(profile.domains),
        "db_ok": health.get("db_ok", False),
        "health": health,
    }


@router.get("/{source_id}/health")
async def source_health(
    source_id: str,
    profile: SourceProfile = Depends(source_db_context),
) -> dict[str, object]:
    from app.api.deps import get_catalog_adapter

    pool_manager = get_pool_manager()
    base_health = await pool_manager.health_check(source_id)
    adapter = get_catalog_adapter(profile)
    pool = await pool_manager.get_pool(source_id)
    details = await adapter.health_details(pool)
    return {**base_health, "details": details}
