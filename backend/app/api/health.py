from fastapi import APIRouter

from app.sources.registry import get_registry

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    registry = get_registry()
    active_sources = [p.id for p in registry.list_profiles() if p.status == "active"]
    return {
        "status": "ok",
        "version": "2.0.0",
        "active_sources": active_sources,
    }
