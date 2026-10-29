#!/usr/bin/env bash
# Local, project-isolated PostgreSQL 16 and Redis for CEKBAO PolicyGuard.
# Data lives in .local/ (git-ignored). Ports: Postgres 55432, Redis 56379.
# Usage: scripts/policyguard_local.sh start|stop|status|reset
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
PGBIN="${PGBIN:-/opt/homebrew/opt/postgresql@16/bin}"
PGDATA="$ROOT/.local/pgdata"
RUN="$ROOT/.local/run"
REDIS_DIR="$ROOT/.local/redis"
PGPORT=55432
REDIS_PORT=56379

start() {
  mkdir -p "$RUN" "$REDIS_DIR"
  if [ ! -f "$PGDATA/PG_VERSION" ]; then
    "$PGBIN/initdb" -D "$PGDATA" -U policyguard --auth=trust --encoding=UTF8 --locale=C >/dev/null
  fi
  if ! "$PGBIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
    "$PGBIN/pg_ctl" -D "$PGDATA" -l "$RUN/postgres.log" -o "-p $PGPORT -k $RUN -c listen_addresses=127.0.0.1 -c max_connections=200" -w start >/dev/null
  fi
  for db in policyguard policyguard_test; do
    "$PGBIN/psql" -h 127.0.0.1 -p $PGPORT -U policyguard -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
      || "$PGBIN/createdb" -h 127.0.0.1 -p $PGPORT -U policyguard "$db"
  done
  if ! redis-cli -p $REDIS_PORT ping >/dev/null 2>&1; then
    redis-server --port $REDIS_PORT --bind 127.0.0.1 --save "" --appendonly no --dir "$REDIS_DIR" --daemonize yes --logfile "$RUN/redis.log" >/dev/null
  fi
  status
}
stop() {
  "$PGBIN/pg_ctl" -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
  redis-cli -p $REDIS_PORT shutdown nosave >/dev/null 2>&1 || true
  echo "stopped"
}
status() {
  "$PGBIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1 && echo "postgres: up on 127.0.0.1:$PGPORT" || echo "postgres: down"
  redis-cli -p $REDIS_PORT ping >/dev/null 2>&1 && echo "redis: up on 127.0.0.1:$REDIS_PORT" || echo "redis: down"
}
case "${1:-status}" in
  start) start ;; stop) stop ;; status) status ;;
  reset) stop; rm -rf "$ROOT/.local"; start ;;
  *) echo "usage: $0 start|stop|status|reset"; exit 2 ;;
esac
