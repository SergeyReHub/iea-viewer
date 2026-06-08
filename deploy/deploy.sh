#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-deploy/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-deploy/docker-compose.yml}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy deploy/.env.example and configure credentials."
  exit 1
fi

bash deploy/stop-v1.sh

echo "=== Deploying iea-viewer-v2 ==="
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d

echo "=== Waiting for backend health ==="
for attempt in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8010/api/health" >/dev/null; then
    break
  fi
  sleep 2
done

if ! curl -sf "http://127.0.0.1:8010/api/health" >/dev/null; then
  echo "Backend health check failed"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=200 backend
  exit 1
fi

PRESET_COUNT="$(curl -sf "http://127.0.0.1:8010/api/v2/sources/iea/presets" | python -c "import json,sys; print(len(json.load(sys.stdin).get('presets', [])))")"
echo "Presets available: $PRESET_COUNT"
if [ "${PRESET_COUNT:-0}" -lt 30 ]; then
  echo "Warning: expected at least 30 presets after seed"
fi

echo "=== Deploy complete ==="
echo "UI:  http://$(hostname -I 2>/dev/null | awk '{print $1}'):5180"
echo "API: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8010/api"
