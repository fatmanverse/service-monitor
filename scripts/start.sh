#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x /opt/homebrew/bin/python3 ]; then
        PYTHON_BIN=/opt/homebrew/bin/python3
    elif [ -x /usr/local/bin/python3 ]; then
        PYTHON_BIN=/usr/local/bin/python3
    else
        PYTHON_BIN=python3
    fi
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    printf '后端要求 Python 3.9+，当前解释器为 %s。\n' "$PYTHON_BIN" >&2
    exit 1
fi
ENV_FILE="$ROOT_DIR/backend/.env"
if [ -f "$ENV_FILE" ]; then
    OVERRIDE_APP_SECRET=${APP_SECRET:-}
    OVERRIDE_INITIAL_ADMIN_PASSWORD=${INITIAL_ADMIN_PASSWORD:-}
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
    if [ -n "$OVERRIDE_APP_SECRET" ]; then
        APP_SECRET=$OVERRIDE_APP_SECRET
        export APP_SECRET
    fi
    if [ -n "$OVERRIDE_INITIAL_ADMIN_PASSWORD" ]; then
        INITIAL_ADMIN_PASSWORD=$OVERRIDE_INITIAL_ADMIN_PASSWORD
        export INITIAL_ADMIN_PASSWORD
    fi
    unset OVERRIDE_APP_SECRET OVERRIDE_INITIAL_ADMIN_PASSWORD
fi
: "${APP_SECRET:?必须设置 APP_SECRET}"
: "${INITIAL_ADMIN_PASSWORD:?必须设置 INITIAL_ADMIN_PASSWORD}"
cd "$ROOT_DIR/backend"
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
