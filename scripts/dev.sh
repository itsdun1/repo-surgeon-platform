#!/usr/bin/env bash
# scripts/dev.sh — one-command local startup.
#
# Brings up Postgres + Redis (via Docker Compose), runs DB migrations, starts
# FastAPI (uvicorn) and the Next.js dashboard. Hit Ctrl+C to stop everything.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load .env.local if present (for SMEE_URL, etc.)
if [ -f .env.local ]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

echo "▶ Starting Docker services (postgres + redis)..."
COMPOSE_PROFILES=""
if [ -n "${SMEE_URL:-}" ]; then
  COMPOSE_PROFILES="--profile tunnel"
  echo "  smee tunnel enabled (SMEE_URL=$SMEE_URL)"
fi
docker compose -f infra/docker-compose.yml $COMPOSE_PROFILES up -d

echo "▶ Waiting for Postgres..."
for i in $(seq 1 30); do
  if docker exec surgeon-postgres pg_isready -U surgeon -d surgeon >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "▶ Running DB migrations..."
cd surgeon-service
if ! command -v uv >/dev/null 2>&1 && ! command -v alembic >/dev/null 2>&1; then
  echo "  Installing Python deps with pip (consider 'uv' for speed)..."
  pip install -e . >/dev/null
fi
alembic upgrade head
cd "$ROOT"

# Start FastAPI in background
echo "▶ Starting surgeon-service on :8000..."
cd surgeon-service
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
cd "$ROOT"

# Start Next.js in background
echo "▶ Starting dashboard on :3000..."
cd dashboard
if [ ! -d node_modules ]; then
  pnpm install
fi
pnpm dev &
DASH_PID=$!
cd "$ROOT"

cleanup() {
  echo ""
  echo "▶ Stopping services..."
  kill $API_PID 2>/dev/null || true
  kill $DASH_PID 2>/dev/null || true
  docker compose -f infra/docker-compose.yml down
}
trap cleanup INT TERM

cat <<EOF

✅ Up and running:

  • surgeon-service:  http://localhost:8000
  • dashboard:        http://localhost:3000
  • postgres:         localhost:5432 (db=surgeon, user=surgeon, pw=dev)
  • redis:            localhost:6379

Logs are streaming below. Hit Ctrl+C to stop everything.

EOF

wait
