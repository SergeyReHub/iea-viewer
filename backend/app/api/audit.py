import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.user_identity import can_view_audit, resolve_current_user
from app.db.context import get_current_source_id

router = APIRouter(tags=["audit"])


def _audit_log_path() -> Path:
    source_id = get_current_source_id()
    path = Path(__file__).resolve().parents[2] / "logs" / "audit" / f"{source_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class AuditEventPayload(BaseModel):
    event_type: str
    page_path: str
    page_name: str | None = None
    session_id: str | None = None
    details: dict[str, object] | None = None


class AuditLogRecord(BaseModel):
    timestamp_utc: str
    full_name: str
    ip: str | None = None
    event_type: str
    page_path: str
    page_name: str | None = None
    session_id: str | None = None
    user_agent: str | None = None
    details: dict[str, object] | None = None


@router.post("/audit/event")
async def write_audit_event(payload: AuditEventPayload, request: Request) -> dict[str, object]:
    current_user = resolve_current_user(request)
    full_name = current_user.get("full_name")
    client_ip = current_user.get("ip")

    if not full_name:
        return {"logged": False, "reason": "unknown_user_ip"}

    log_path = _audit_log_path()
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "full_name": full_name,
        "ip": client_ip,
        "source_id": get_current_source_id(),
        "event_type": payload.event_type,
        "page_path": payload.page_path,
        "page_name": payload.page_name,
        "session_id": payload.session_id,
        "user_agent": request.headers.get("user-agent"),
        "details": payload.details,
    }
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"logged": True}


@router.get("/audit/logs")
async def read_audit_logs(request: Request) -> dict[str, list[AuditLogRecord]]:
    current_user = resolve_current_user(request)
    if not can_view_audit(current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    log_path = _audit_log_path()
    if not log_path.exists():
        return {"records": []}

    records: list[AuditLogRecord] = []
    with log_path.open("r", encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                records.append(AuditLogRecord(**payload))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    records.reverse()
    return {"records": records}
