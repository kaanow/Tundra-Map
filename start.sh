#!/bin/sh
# Verbose startup so Railway logs show exactly what happened.
set -e
echo "=== container starting ==="
echo "PORT=${PORT:-<unset>}"
echo "DATABASE_URL=${DATABASE_URL:+set (${#DATABASE_URL} chars)}"
echo "DATABASE_URL=${DATABASE_URL:-<unset>}" | head -c 60; echo
echo "PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-<unset>}"
echo "SHARED_SECRET=${SHARED_SECRET:+set (${#SHARED_SECRET} chars)}"
echo "cwd=$(pwd)"

echo "=== running migrations ==="
python -u -m app.migrate
echo "=== migrations ok ==="

echo "=== starting uvicorn on 0.0.0.0:${PORT:-8000} ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info --no-access-log
