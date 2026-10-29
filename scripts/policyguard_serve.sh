#!/usr/bin/env bash
# Run CEKBAO with PolicyGuard locally: services, migrations, synthetic seed, one worker, web server.
# Usage: scripts/policyguard_serve.sh [port]   (default 8780). Ctrl+C stops the web server and the worker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${1:-${PORT:-8780}}"
export PG_ENABLED=1
export CEKBAO_DB_PATH="${CEKBAO_DB_PATH:-$ROOT/data/policyguard_demo.sqlite3}"
export PG_STORAGE_DIR="${PG_STORAGE_DIR:-$ROOT/.local/objects}"

scripts/policyguard_local.sh start >/dev/null
.venv/bin/alembic upgrade head
.venv/bin/python -m policyguard.seed

.venv/bin/python -m policyguard.worker &
WORKER=$!
trap 'kill $WORKER 2>/dev/null || true' EXIT INT TERM

.venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port "$PORT" --no-access-log
