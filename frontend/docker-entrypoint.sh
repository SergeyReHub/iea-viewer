#!/bin/sh
set -eu

cd /app

if [ ! -f package.json ]; then
  echo "package.json not found in /app"
  exit 1
fi

HASH_FILE="/app/node_modules/.package_json.sha256"
CURRENT_HASH="$(sha256sum package.json | awk '{print $1}')"
INSTALLED_HASH=""

if [ -f "$HASH_FILE" ]; then
  INSTALLED_HASH="$(cat "$HASH_FILE")"
fi

if [ ! -d /app/node_modules ] || [ "$CURRENT_HASH" != "$INSTALLED_HASH" ]; then
  echo "Installing frontend dependencies (package.json changed or first run)..."
  npm install
  printf "%s" "$CURRENT_HASH" > "$HASH_FILE"
else
  echo "Skipping npm install: dependencies are up to date."
fi

exec npm run dev -- --host 0.0.0.0 --port 5180
