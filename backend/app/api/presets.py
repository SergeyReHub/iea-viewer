import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.context import get_current_source_id
from app.services.preset_adaptation import adapt_v1_preset

router = APIRouter(tags=["presets"])


def _presets_dir() -> Path:
    source_id = get_current_source_id()
    path = Path(__file__).resolve().parents[2] / "data" / "presets" / source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


LEGACY_PRESETS_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_presets.json"
STORE_LOCK = Lock()


class PresetRecord(BaseModel):
    id: str
    name: str
    description: str = ""
    factTable: str
    selectedFilterValues: dict[str, list[str]] = Field(default_factory=dict)
    pivotLayout: str = "time_rows_filters_columns"
    periodFrom: str = ""
    periodTo: str = ""
    periodSort: str = "asc"
    updatedAt: str
    version: int = Field(ge=1)


class PresetMutationPayload(BaseModel):
    id: str
    name: str
    description: str = ""
    factTable: str
    selectedFilterValues: dict[str, list[str]] = Field(default_factory=dict)
    pivotLayout: str = "time_rows_filters_columns"
    periodFrom: str = ""
    periodTo: str = ""
    periodSort: str = "asc"


class PresetUpdatePayload(BaseModel):
    name: str
    description: str = ""
    factTable: str
    selectedFilterValues: dict[str, list[str]] = Field(default_factory=dict)
    pivotLayout: str = "time_rows_filters_columns"
    periodFrom: str = ""
    periodTo: str = ""
    periodSort: str = "asc"
    expectedVersion: int | None = Field(default=None, ge=1)
    expectedUpdatedAt: str | None = None
    conflictStrategy: Literal["reject", "copy"] = "copy"


class PresetListPayload(BaseModel):
    presets: list[PresetRecord] = Field(default_factory=list)


class PresetImportPayload(BaseModel):
    presets: list[PresetMutationPayload] = Field(default_factory=list)
    merge: bool = True


class PresetUpdateResponse(BaseModel):
    mode: Literal["updated", "copied_on_conflict"]
    preset: PresetRecord
    sourcePresetId: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preset_file_path(preset_id: str) -> Path:
    safe_name = quote(preset_id, safe="")
    return _presets_dir() / f"{safe_name}.json"


def _ensure_store_dir() -> None:
    _presets_dir().mkdir(parents=True, exist_ok=True)


def _write_json_atomic(path: Path, payload: dict) -> None:
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _normalize_record(raw: dict) -> PresetRecord:
    selected_filter_values = raw.get("selectedFilterValues")
    if not isinstance(selected_filter_values, dict):
        selected_filter_values = {}
    normalized_filters = {
        str(key): [str(value) for value in values] if isinstance(values, list) else []
        for key, values in selected_filter_values.items()
    }
    return PresetRecord(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        factTable=str(raw.get("factTable", "")),
        selectedFilterValues=normalized_filters,
        pivotLayout=(
            "time_columns_filters_rows"
            if str(raw.get("pivotLayout")) == "time_columns_filters_rows"
            else "time_rows_filters_columns"
        ),
        periodFrom=str(raw.get("periodFrom", "")),
        periodTo=str(raw.get("periodTo", "")),
        periodSort="desc" if str(raw.get("periodSort")) == "desc" else "asc",
        updatedAt=str(raw.get("updatedAt") or _now_iso()),
        version=int(raw.get("version") or 1),
    )


def _read_preset(preset_id: str) -> PresetRecord | None:
    path = _preset_file_path(preset_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return _normalize_record(raw)
    except Exception:
        return None


def _write_preset(record: PresetRecord) -> None:
    _ensure_store_dir()
    path = _preset_file_path(record.id)
    _write_json_atomic(path, record.model_dump())


def _delete_preset(preset_id: str) -> bool:
    path = _preset_file_path(preset_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def _list_presets() -> list[PresetRecord]:
    _ensure_store_dir()
    presets: list[PresetRecord] = []
    for path in _presets_dir().glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                continue
            presets.append(_normalize_record(raw))
        except Exception:
            continue
    presets.sort(key=lambda item: (item.updatedAt, item.id), reverse=True)
    return presets


def _next_copy_name(source_name: str, existing_names: set[str]) -> str:
    base_name = source_name.strip() or "Новый пресет"
    pattern = re.compile(re.escape(base_name) + r" \(копия (\d+)\)$")
    max_index = 0
    if base_name in existing_names:
        max_index = 1
    for name in existing_names:
        match = pattern.fullmatch(name)
        if not match:
            continue
        max_index = max(max_index, int(match.group(1)))
    next_index = max_index if max_index > 0 else 0
    while True:
        next_index += 1
        candidate = f"{base_name} (копия {next_index})"
        if candidate not in existing_names:
            return candidate


def _extract_legacy_presets(raw_store: dict) -> list[PresetMutationPayload]:
    direct_presets = raw_store.get("presets")
    candidates: list[dict] = []
    if isinstance(direct_presets, list):
        candidates.extend([item for item in direct_presets if isinstance(item, dict)])

    users = raw_store.get("users")
    if isinstance(users, dict):
        merged: dict[str, dict] = {}
        for user_payload in users.values():
            if not isinstance(user_payload, dict):
                continue
            user_presets = user_payload.get("presets")
            if not isinstance(user_presets, list):
                continue
            for item in user_presets:
                if not isinstance(item, dict):
                    continue
                preset_id = item.get("id")
                if isinstance(preset_id, str) and preset_id:
                    merged[preset_id] = item
        candidates.extend(merged.values())

    parsed: list[PresetMutationPayload] = []
    for item in candidates:
        try:
            parsed.append(PresetMutationPayload(**item))
        except Exception:
            continue
    deduped: dict[str, PresetMutationPayload] = {}
    for item in parsed:
        deduped[item.id] = item
    return list(deduped.values())


def _migrate_legacy_store_if_needed() -> None:
    if not LEGACY_PRESETS_STORE_PATH.exists():
        return
    if any(_presets_dir().glob("*.json")):
        return
    try:
        raw = json.loads(LEGACY_PRESETS_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(raw, dict):
        return
    legacy_presets = _extract_legacy_presets(raw)
    if not legacy_presets:
        return
    for item in legacy_presets:
        record = PresetRecord(
            id=item.id,
            name=item.name,
            description=item.description,
            factTable=item.factTable,
            selectedFilterValues=item.selectedFilterValues,
            pivotLayout=item.pivotLayout,
            periodFrom=item.periodFrom,
            periodTo=item.periodTo,
            periodSort=item.periodSort,
            updatedAt=_now_iso(),
            version=1,
        )
        _write_preset(record)


@router.get("/presets")
async def get_presets() -> PresetListPayload:
    with STORE_LOCK:
        _ensure_store_dir()
        _migrate_legacy_store_if_needed()
        return PresetListPayload(presets=_list_presets())


@router.post("/presets")
async def create_preset(payload: PresetMutationPayload) -> PresetRecord:
    with STORE_LOCK:
        _ensure_store_dir()
        if _read_preset(payload.id) is not None:
            raise HTTPException(status_code=409, detail="Preset with this id already exists")
        adapted = adapt_v1_preset(payload.model_dump())
        record = PresetRecord(
            id=adapted["id"],
            name=adapted["name"],
            description=adapted["description"],
            factTable=adapted["factTable"],
            selectedFilterValues=adapted["selectedFilterValues"],
            pivotLayout=adapted["pivotLayout"],
            periodFrom=adapted["periodFrom"],
            periodTo=adapted["periodTo"],
            periodSort=adapted["periodSort"],
            updatedAt=_now_iso(),
            version=1,
        )
        _write_preset(record)
        return record


@router.patch("/presets/{preset_id}")
async def update_preset(preset_id: str, payload: PresetUpdatePayload) -> PresetUpdateResponse:
    with STORE_LOCK:
        current = _read_preset(preset_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Preset not found")
        if payload.expectedVersion is None and payload.expectedUpdatedAt is None:
            raise HTTPException(status_code=400, detail="expectedVersion or expectedUpdatedAt is required")

        version_matches = payload.expectedVersion is None or payload.expectedVersion == current.version
        updated_matches = (
            payload.expectedUpdatedAt is None or payload.expectedUpdatedAt == current.updatedAt
        )
        if version_matches and updated_matches:
            updated = PresetRecord(
                id=current.id,
                name=payload.name,
                description=payload.description,
                factTable=payload.factTable,
                selectedFilterValues=payload.selectedFilterValues,
                pivotLayout=payload.pivotLayout,
                periodFrom=payload.periodFrom,
                periodTo=payload.periodTo,
                periodSort=payload.periodSort,
                updatedAt=_now_iso(),
                version=current.version + 1,
            )
            _write_preset(updated)
            return PresetUpdateResponse(mode="updated", preset=updated)

        if payload.conflictStrategy != "copy":
            raise HTTPException(status_code=409, detail="Preset was changed by another user/session")

        existing_names = {item.name for item in _list_presets()}
        copied = PresetRecord(
            id=f"{preset_id}-copy-{uuid4().hex[:8]}",
            name=_next_copy_name(payload.name or current.name, existing_names),
            description=payload.description,
            factTable=payload.factTable,
            selectedFilterValues=payload.selectedFilterValues,
            pivotLayout=payload.pivotLayout,
            periodFrom=payload.periodFrom,
            periodTo=payload.periodTo,
            periodSort=payload.periodSort,
            updatedAt=_now_iso(),
            version=1,
        )
        _write_preset(copied)
        return PresetUpdateResponse(
            mode="copied_on_conflict",
            preset=copied,
            sourcePresetId=current.id,
        )


@router.delete("/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    expectedVersion: int | None = Query(default=None, ge=1),
    expectedUpdatedAt: str | None = Query(default=None),
) -> dict[str, object]:
    with STORE_LOCK:
        current = _read_preset(preset_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Preset not found")
        if expectedVersion is None and expectedUpdatedAt is None:
            raise HTTPException(status_code=400, detail="expectedVersion or expectedUpdatedAt is required")

        version_matches = expectedVersion is None or expectedVersion == current.version
        updated_matches = expectedUpdatedAt is None or expectedUpdatedAt == current.updatedAt
        if not (version_matches and updated_matches):
            raise HTTPException(status_code=409, detail="Preset was changed by another user/session")

        _delete_preset(preset_id)
        return {"deleted": True}


@router.post("/presets/import")
async def import_presets(payload: PresetImportPayload) -> PresetListPayload:
    with STORE_LOCK:
        _ensure_store_dir()
        if not payload.merge:
            for preset_file in _presets_dir().glob("*.json"):
                preset_file.unlink()
        for item in payload.presets:
            adapted = adapt_v1_preset(item.model_dump())
            current = _read_preset(adapted["id"])
            next_version = (current.version + 1) if current else 1
            record = PresetRecord(
                id=adapted["id"],
                name=adapted["name"],
                description=adapted["description"],
                factTable=adapted["factTable"],
                selectedFilterValues=adapted["selectedFilterValues"],
                pivotLayout=adapted["pivotLayout"],
                periodFrom=adapted["periodFrom"],
                periodTo=adapted["periodTo"],
                periodSort=adapted["periodSort"],
                updatedAt=_now_iso(),
                version=next_version,
            )
            _write_preset(record)
        return PresetListPayload(presets=_list_presets())


@router.get("/presets/export")
async def export_presets() -> dict[str, object]:
    with STORE_LOCK:
        presets = _list_presets()
    return {
        "exported_at": _now_iso(),
        "presets": [item.model_dump() for item in presets],
    }


@router.put("/presets")
async def save_presets(payload: PresetListPayload) -> dict[str, object]:
    """
    Legacy bulk-replace endpoint. Kept for compatibility.
    """
    with STORE_LOCK:
        _ensure_store_dir()
        for preset_file in _presets_dir().glob("*.json"):
            preset_file.unlink()
        for item in payload.presets:
            record = PresetRecord(
                id=item.id,
                name=item.name,
                description=item.description,
                factTable=item.factTable,
                selectedFilterValues=item.selectedFilterValues,
                pivotLayout=item.pivotLayout,
                periodFrom=item.periodFrom,
                periodTo=item.periodTo,
                periodSort=item.periodSort,
                updatedAt=_now_iso(),
                version=1,
            )
            _write_preset(record)
    return {"saved": True, "count": len(payload.presets)}
