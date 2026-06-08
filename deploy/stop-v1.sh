#!/usr/bin/env bash
# Stop legacy iea-viewer v1 containers before v2 takes ports 8010/5180.
set -euo pipefail

echo "=== Stopping iea-viewer v1 ==="

if [ -n "${V1_COMPOSE_DIR:-}" ] && [ -f "${V1_COMPOSE_DIR}/deploy/docker-compose.yml" ]; then
  ENV_FILE="${V1_COMPOSE_DIR}/deploy/.env"
  if [ -f "$ENV_FILE" ]; then
    docker compose --env-file "$ENV_FILE" -f "${V1_COMPOSE_DIR}/deploy/docker-compose.yml" down --remove-orphans || true
  else
    docker compose -f "${V1_COMPOSE_DIR}/deploy/docker-compose.yml" down --remove-orphans || true
  fi
fi

for container in iea-viewer-backend iea-viewer-frontend; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$container"; then
    echo "Removing container $container"
    docker rm -f "$container" || true
  fi
done

echo "=== v1 stopped ==="
