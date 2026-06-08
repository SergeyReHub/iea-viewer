from fastapi import APIRouter, Query

from app.db.connection import fetch_query_rows

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/load-batches")
async def list_load_batches(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, object]:
    rows = await fetch_query_rows(
        """
        SELECT
            lb.batch_id,
            lb.source_id,
            lb.domain,
            lb.file_name,
            lb.file_hash,
            lb.status,
            lb.records_read,
            lb.records_inserted,
            lb.records_updated,
            lb.records_skipped,
            lb.records_error,
            lb.started_at,
            lb.completed_at,
            lb.error_message,
            lb.created_by,
            ds.source_code,
            ds.source_name
        FROM base.load_batch lb
        LEFT JOIN base.ref_data_source ds ON ds.source_id = lb.source_id
        ORDER BY lb.started_at DESC NULLS LAST, lb.batch_id DESC
        LIMIT $1
        """,
        limit,
    )
    return {"count": len(rows), "rows": rows}


@router.get("/validation-errors")
async def list_validation_errors(
    batch_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, object]:
    if batch_id is not None:
        rows = await fetch_query_rows(
            """
            SELECT
                error_id,
                batch_id,
                error_type,
                error_severity,
                record_data,
                error_message,
                table_name,
                created_at
            FROM base.validation_error
            WHERE batch_id = $1
            ORDER BY error_id DESC
            LIMIT $2
            """,
            batch_id,
            limit,
        )
    else:
        rows = await fetch_query_rows(
            """
            SELECT
                error_id,
                batch_id,
                error_type,
                error_severity,
                record_data,
                error_message,
                table_name,
                created_at
            FROM base.validation_error
            ORDER BY error_id DESC
            LIMIT $1
            """,
            limit,
        )
    return {"count": len(rows), "rows": rows}


@router.get("/freshness")
async def data_freshness() -> dict[str, object]:
    rows = await fetch_query_rows(
        """
        SELECT
            ds.domain,
            ds.source_code,
            ds.source_name,
            ds.is_primary,
            MAX(lb.completed_at) AS last_completed_at,
            COUNT(lb.batch_id) FILTER (WHERE lb.status = 'COMPLETED') AS completed_batches
        FROM base.ref_data_source ds
        LEFT JOIN base.load_batch lb ON lb.source_id = ds.source_id
        GROUP BY ds.source_id, ds.domain, ds.source_code, ds.source_name, ds.is_primary
        ORDER BY ds.domain, ds.is_primary DESC, ds.source_code
        """
    )
    return {"count": len(rows), "rows": rows}


@router.get("/primary-sources")
async def primary_sources(domain: str | None = Query(default=None)) -> dict[str, object]:
    if domain:
        rows = await fetch_query_rows(
            """
            SELECT source_id, source_code, source_name, domain, is_primary
            FROM base.ref_data_source
            WHERE domain = $1
            ORDER BY is_primary DESC, source_code
            """,
            domain,
        )
    else:
        rows = await fetch_query_rows(
            """
            SELECT source_id, source_code, source_name, domain, is_primary
            FROM base.ref_data_source
            ORDER BY domain, is_primary DESC, source_code
            """
        )
    return {"count": len(rows), "rows": rows}
