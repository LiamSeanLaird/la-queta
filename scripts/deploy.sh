#!/usr/bin/env bash
# Day-2 deploy on the production VM. See DEPLOY.md.
# Usage (on the server):
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --no-pull
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_PULL=0
for arg in "$@"; do
  case "$arg" in
    --no-pull) NO_PULL=1 ;;
    -h|--help)
      echo "Usage: $0 [--no-pull]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

ENV_FILE="${LA_QUETA_ENV_FILE:-/etc/la-queta/env}"
HEALTH_URL="${LA_QUETA_HEALTH_URL:-http://127.0.0.1/api/health}"
SERVICE="${LA_QUETA_SERVICE:-la-queta}"
DB_PATH="${LA_QUETA_DB_PATH:-/var/lib/la-queta/app.db}"
BACKUP_DIR="${LA_QUETA_BACKUP_DIR:-/var/lib/la-queta/backups}"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Missing $ROOT/.venv — create/activate the production venv first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ "$NO_PULL" -eq 0 ]]; then
  echo "==> git pull"
  git pull --ff-only
else
  echo "==> skipping git pull"
fi

echo "==> poetry install --only main"
poetry install --only main

if [[ -f "$DB_PATH" ]] && command -v sqlite3 >/dev/null 2>&1; then
  mkdir -p "$BACKUP_DIR"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  echo "==> sqlite backup → $BACKUP_DIR/app-pre-deploy-$stamp.db"
  sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/app-pre-deploy-$stamp.db'"
fi

echo "==> flask db upgrade"
flask --app wsgi db upgrade

echo "==> seed"
python scripts/seed.py

if systemctl list-unit-files "${SERVICE}.service" 2>/dev/null | grep -q "${SERVICE}.service"; then
  echo "==> systemctl restart $SERVICE"
  sudo systemctl restart "$SERVICE"
  # brief settle for workers
  sleep 1
else
  echo "==> no ${SERVICE}.service — skip restart (not on prod?)"
fi

echo "==> health $HEALTH_URL"
if ! curl -sf "$HEALTH_URL" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  echo "Health check failed" >&2
  curl -sS "$HEALTH_URL" >&2 || true
  exit 1
fi

echo "Deploy OK ($(git rev-parse --short HEAD))"
