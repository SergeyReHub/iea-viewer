import json
from functools import lru_cache
from typing import TypedDict

from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter(tags=["user-identity"])

DEFAULT_IP_TO_FULL_NAME: dict[str, str] = {
    "192.168.235.159": "Сенкевич Натэлла Геннадьевна",
    "192.168.235.62": "Микульская Влада Игоревна",
    "192.168.235.67": "Михайлов Богдан Сергеевич",
    "192.168.235.89": "Кудряшов Всеволод Владимирович",
    "192.168.235.148": "Матвиевский Павел Владимирович",
}

DEFAULT_AUDIT_VIEWER_IPS = {
    "192.168.235.148",
    "192.168.235.89",
}


def normalize_ip(ip: str) -> str:
    if ip.startswith("::ffff:"):
        return ip.split("::ffff:", 1)[1]
    return ip


@lru_cache
def get_ip_to_full_name_map() -> dict[str, str]:
    mapping = dict(DEFAULT_IP_TO_FULL_NAME)
    extra_raw = settings.identity_ip_map_extra.strip()
    if not extra_raw:
        return mapping
    try:
        extra = json.loads(extra_raw)
    except json.JSONDecodeError:
        return mapping
    if not isinstance(extra, dict):
        return mapping
    for ip, name in extra.items():
        if ip and name:
            mapping[str(ip)] = str(name)
    return mapping


@lru_cache
def get_audit_viewer_ips() -> set[str]:
    ips = set(DEFAULT_AUDIT_VIEWER_IPS)
    extra_raw = settings.audit_viewer_ips.strip()
    if not extra_raw:
        return ips
    for item in extra_raw.split(","):
        candidate = normalize_ip(item.strip())
        if candidate:
            ips.add(candidate)
    return ips


class CurrentUser(TypedDict):
    ip: str | None
    full_name: str | None
    can_view_audit: bool


def can_view_audit(user: dict[str, str | None]) -> bool:
    client_ip = user.get("ip")
    if client_ip and client_ip in get_audit_viewer_ips():
        return True
    full_name = (user.get("full_name") or "").strip().lower()
    return "кудряшов" in full_name or "kudryashov" in full_name


def resolve_client_ip(request: Request) -> str:
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return normalize_ip(real_ip)

    forwarded_for = request.headers.get("x-forwarded-for", "")
    candidate_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    if candidate_ip:
        return normalize_ip(candidate_ip)

    if request.client and request.client.host:
        return normalize_ip(request.client.host)
    return ""


def resolve_current_user(request: Request) -> CurrentUser:
    client_ip = resolve_client_ip(request)
    full_name = get_ip_to_full_name_map().get(client_ip)
    payload: dict[str, str | None] = {
        "ip": client_ip or None,
        "full_name": full_name,
    }
    return {
        **payload,
        "can_view_audit": can_view_audit(payload),
    }


@router.get("/whoami")
async def whoami(request: Request) -> CurrentUser:
    return resolve_current_user(request)
