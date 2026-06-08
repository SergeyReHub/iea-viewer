from fastapi import APIRouter, Depends

from app.api import (
    audit,
    documents,
    master_report,
    meta,
    presets,
    raw,
    reference,
    user_identity,
)
from app.api.deps import source_db_context
from app.api.v2 import admin

source_scoped_router = APIRouter(
    prefix="/sources/{source_id}",
    dependencies=[Depends(source_db_context)],
)

source_scoped_router.include_router(meta.router)
source_scoped_router.include_router(reference.router)
source_scoped_router.include_router(raw.router)
source_scoped_router.include_router(master_report.router)
source_scoped_router.include_router(presets.router)
source_scoped_router.include_router(audit.router)
source_scoped_router.include_router(user_identity.router)
source_scoped_router.include_router(documents.router)
source_scoped_router.include_router(admin.router)

v2_router = APIRouter(prefix="/v2")
v2_router.include_router(source_scoped_router)
