#!/usr/bin/env bash
set -euo pipefail

cd /app/surgeon-service

echo "▶ Running migrations..."
alembic upgrade head || { echo "migrations failed"; exit 1; }

echo "▶ Verifying gitagent CLI..."
if ! command -v gitagent >/dev/null 2>&1; then
  echo "✗ gitagent CLI not found in PATH"
  exit 1
fi
gitagent --version 2>/dev/null | head -1 || true

echo "▶ Starting uvicorn on :18000..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 18000 \
    --proxy-headers \
    --log-level info
