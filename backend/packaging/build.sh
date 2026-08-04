#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
OUTPUT_DIR=${OUTPUT_DIR:-"$ROOT_DIR/dist/server"}
ARTIFACT_NAME=${ARTIFACT_NAME:?ARTIFACT_NAME is required}
if [ -z "${PYTHON_BIN:-}" ]; then
    for candidate in /opt/python/cp39-cp39/bin/python /opt/python/cp310-cp310/bin/python python3; do
        if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
            PYTHON_BIN=$candidate
            break
        fi
    done
fi
: "${PYTHON_BIN:?No supported Python interpreter found}"

if [ ! -f "$ROOT_DIR/frontend/dist/index.html" ]; then
    printf '%s\n' 'frontend/dist 不存在；请先运行 npm build。' >&2
    exit 1
fi

cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m pip install --disable-pip-version-check --no-cache-dir -r requirements-build.txt
cd "$ROOT_DIR"
rm -rf "$OUTPUT_DIR/work"
mkdir -p "$OUTPUT_DIR/work" "$OUTPUT_DIR"

"$PYTHON_BIN" -m PyInstaller \
    --clean \
    --noconfirm \
    --onefile \
    --name service-monitor-server \
    --paths backend \
    --add-data "$ROOT_DIR/frontend/dist:frontend/dist" \
    --collect-submodules app \
    --collect-submodules uvicorn \
    --distpath "$OUTPUT_DIR/work/dist" \
    --workpath "$OUTPUT_DIR/work/build" \
    --specpath "$OUTPUT_DIR/work" \
    backend/packaging/entrypoint.py

install -m 0755 "$OUTPUT_DIR/work/dist/service-monitor-server" "$OUTPUT_DIR/$ARTIFACT_NAME"
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$OUTPUT_DIR" && sha256sum "$ARTIFACT_NAME" > "$ARTIFACT_NAME.sha256")
else
    (cd "$OUTPUT_DIR" && shasum -a 256 "$ARTIFACT_NAME" > "$ARTIFACT_NAME.sha256")
fi
"$OUTPUT_DIR/$ARTIFACT_NAME" --self-test
