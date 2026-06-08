#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.preset_adaptation import adapt_v1_preset  # noqa: E402


def _preset_file_path(presets_dir: Path, preset_id: str) -> Path:
    return presets_dir / f"{quote(preset_id, safe='')}.json"


def migrate(
    *,
    export_path: Path,
    presets_dir: Path,
    remove_demo: bool = True,
) -> int:
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list):
        raise ValueError("Export file does not contain a presets array")

    presets_dir.mkdir(parents=True, exist_ok=True)

    if remove_demo:
        for path in presets_dir.glob("demo-*.json"):
            path.unlink()

    for path in presets_dir.glob("*.json"):
        path.unlink()

    written = 0
    for raw_preset in raw_presets:
        if not isinstance(raw_preset, dict):
            continue
        adapted = adapt_v1_preset(raw_preset)
        if not adapted["id"]:
            continue
        if not adapted.get("updatedAt"):
            adapted["updatedAt"] = datetime.now(timezone.utc).isoformat()
        target = _preset_file_path(presets_dir, adapted["id"])
        target.write_text(json.dumps(adapted, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate IEA Viewer v1 presets into v2 storage")
    parser.add_argument(
        "--export",
        default=str(ROOT / "scripts" / "v1_presets_export.json"),
        help="Path to v1 /api/presets/export JSON",
    )
    parser.add_argument(
        "--target",
        default=str(ROOT / "backend" / "data" / "presets" / "iea"),
        help="Target presets directory for source iea",
    )
    args = parser.parse_args()

    count = migrate(
        export_path=Path(args.export),
        presets_dir=Path(args.target),
        remove_demo=True,
    )
    print(f"Migrated {count} presets into {args.target}")


if __name__ == "__main__":
    main()
