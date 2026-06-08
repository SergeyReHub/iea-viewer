# Multi-source architecture

## Components

| Component | Path | Role |
|-----------|------|------|
| SourceRegistry | `backend/app/sources/registry.py` | Loads `config/sources.yaml` |
| ConnectionPoolManager | `backend/app/sources/pool_manager.py` | asyncpg pools per active source |
| CatalogAdapter | `backend/app/sources/adapters/` | Domain/table catalog per source type |
| DB context | `backend/app/db/context.py` | ContextVar for current pool |
| v2 router | `backend/app/api/v2/router.py` | Source-scoped API mount |

## Request flow

1. Client calls `/api/v2/sources/iea/meta/domains`
2. FastAPI resolves `source_id`, checks `status=active`
3. `source_db_context` sets pool for handler
4. Handler uses `get_pool()` from context (same code as v1)

## Planned sources

`status=planned` → no pool, API data endpoints return **503** with profile metadata. UI shows cards at `/planned-sources`.

## Adding a new source (Phase 4)

1. Implement ETL + PostgreSQL schema
2. Create `CatalogAdapter` subclass
3. Set `{ID}_DB_URL` in env
4. Change `status: active` in `sources.yaml`
