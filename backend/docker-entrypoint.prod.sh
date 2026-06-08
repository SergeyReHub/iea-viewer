#!/bin/sh
set -e

PRESETS_DIR=/app/data/presets/iea
SEED_DIR=/app/seed/presets/iea

if [ -d "$SEED_DIR" ]; then
  mkdir -p "$PRESETS_DIR"
  if [ -z "$(ls -A "$PRESETS_DIR" 2>/dev/null)" ] || [ "${FORCE_SEED_PRESETS:-}" = "true" ]; then
    cp -a "$SEED_DIR"/. "$PRESETS_DIR"/
    echo "Presets ready in $PRESETS_DIR ($(ls -1 "$PRESETS_DIR" | wc -l | tr -d ' ') files)"
  fi
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8010
