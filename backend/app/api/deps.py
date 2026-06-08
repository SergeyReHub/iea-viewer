from __future__ import annotations

from fastapi import Depends, HTTPException

from app.db.context import clear_db_context, set_db_context
from app.sources.adapters.iea_etl import get_adapter
from app.sources.pool_manager import get_pool_manager
from app.sources.registry import SourceProfile, get_registry


def resolve_source(source_id: str) -> SourceProfile:
    registry = get_registry()
    profile = registry.get(source_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_id}")
    return profile


async def require_active_source(source_id: str) -> SourceProfile:
    profile = resolve_source(source_id)
    if profile.status != "active":
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Source is not active yet",
                "source_id": profile.id,
                "name": profile.name,
                "status": profile.status,
                "homepage_url": profile.homepage_url,
                "description": profile.description,
            },
        )
    return profile


async def source_db_context(
    source_id: str,
    profile: SourceProfile = Depends(require_active_source),
) -> SourceProfile:
    pool_manager = get_pool_manager()
    pool = await pool_manager.get_pool(source_id)
    set_db_context(source_id, pool)
    try:
        yield profile
    finally:
        clear_db_context()


def get_catalog_adapter(profile: SourceProfile):
    return get_adapter(profile.adapter)
