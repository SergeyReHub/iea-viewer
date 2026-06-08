from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.master_report import router as master_report_router
from app.api.meta import router as meta_router
from app.api.presets import router as presets_router
from app.api.reference import router as reference_router
from app.api.raw import router as raw_router
from app.api.user_identity import router as user_identity_router
from app.api.v2 import router as v2_api_router
from app.core.config import settings
from app.sources.pool_manager import get_pool_manager

app = FastAPI(title=settings.app_name, version="2.0.0")

allow_origins = (
    ["*"]
    if settings.cors_origins.strip() == "*"
    else [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(v2_api_router, prefix="/api")

# Legacy v1 routes (single default IEA connection via context on first active source)
app.include_router(audit_router, prefix="/api")
app.include_router(master_report_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(presets_router, prefix="/api")
app.include_router(reference_router, prefix="/api")
app.include_router(raw_router, prefix="/api")
app.include_router(user_identity_router, prefix="/api")
app.include_router(documents_router, prefix="/api")


@app.on_event("startup")
async def startup_event() -> None:
    pool_manager = get_pool_manager()
    await pool_manager.init_all()
    # Legacy v1: set default context to IEA if active
    from app.db.context import set_db_context
    from app.sources.registry import get_registry

    registry = get_registry()
    iea = registry.get("iea")
    if iea and iea.status == "active":
        pool = await pool_manager.get_pool("iea")
        set_db_context("iea", pool)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await get_pool_manager().close_all()
