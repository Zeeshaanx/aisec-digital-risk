#!/bin/bash
set -e

PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGDB="${POSTGRES_DB:-media_intel}"

echo "[fastapi] Waiting for PostgreSQL..."
until PGPASSWORD="$PGPASSWORD" psql -h 127.0.0.1 -U "$PGUSER" -d "$PGDB" -c '\q' 2>/dev/null; do
    echo "[fastapi] PostgreSQL not ready, retrying in 2s..."
    sleep 2
done
echo "[fastapi] PostgreSQL ready."

echo "[fastapi] Waiting for Redis..."
until redis-cli ping 2>/dev/null | grep -q PONG; do
    sleep 1
done
echo "[fastapi] Redis ready."

# Export env vars with localhost instead of container names
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://$PGUSER:$PGPASSWORD@127.0.0.1:5432/$PGDB}"
export DATABASE_URL_SYNC="${DATABASE_URL_SYNC:-postgresql://$PGUSER:$PGPASSWORD@127.0.0.1:5432/$PGDB}"
export SEARXNG_URL="${SEARXNG_URL:-http://127.0.0.1:8080/}"

echo "[fastapi] Running Alembic migrations..."
cd /app
python -m alembic upgrade head

echo "[fastapi] Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
