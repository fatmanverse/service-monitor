#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -z "${NODE_BIN:-}" ]; then
    if [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/node" ]; then
        NODE_BIN="$CONDA_PREFIX/bin/node"
    elif [ -x "$HOME/miniconda3/bin/node" ]; then
        NODE_BIN="$HOME/miniconda3/bin/node"
    elif [ -x /root/miniconda3/bin/node ]; then
        NODE_BIN=/root/miniconda3/bin/node
    elif command -v node >/dev/null 2>&1; then
        NODE_BIN=$(command -v node)
    else
        NODE_BIN=''
    fi
fi
if [ -z "${NPM_BIN:-}" ]; then
    if [ -n "${CONDA_PREFIX:-}" ] && [ -x "$CONDA_PREFIX/bin/npm" ]; then
        NPM_BIN="$CONDA_PREFIX/bin/npm"
    elif [ -x "$(dirname "$NODE_BIN")/npm" ]; then
        NPM_BIN="$(dirname "$NODE_BIN")/npm"
    elif command -v npm >/dev/null 2>&1; then
        NPM_BIN=$(command -v npm)
    else
        NPM_BIN=''
    fi
fi
if [ -z "$NODE_BIN" ] || [ -z "$NPM_BIN" ]; then
    printf '未找到 Node.js/npm。前端构建要求 Node.js 20.19+ 或 22.12+。\n' >&2
    exit 1
fi
PATH="$(dirname "$NODE_BIN"):$PATH"
export PATH
if ! NODE_VERSION=$("$NODE_BIN" -p 'process.versions.node' 2>&1); then
    printf 'Node.js 可执行文件无法在当前系统运行：\n%s\n' "$NODE_VERSION" >&2
    printf '%s\n' '旧版 Linux 请勿使用 NVM 官方二进制，可执行: nvm deactivate && conda install -n base -c conda-forge "nodejs>=20.19,<21"' >&2
    exit 1
fi
printf '使用 Node.js: %s\n' "$NODE_VERSION"
printf 'Node.js 路径: %s\n' "$NODE_BIN"
if ! "$NODE_BIN" -e 'var v = process.versions.node.split(".").map(Number); var ok = (v[0] === 20 && v[1] >= 19) || (v[0] === 22 && v[1] >= 12) || v[0] > 22; process.exit(ok ? 0 : 1)'; then
    printf 'Node.js %s 不受支持。请升级到 Node.js 20.19+ 或 22.12+。\n' "$NODE_VERSION" >&2
    printf '%s\n' 'Conda 环境可执行: conda install -c conda-forge "nodejs>=20.19,<21"' >&2
    exit 1
fi
if ! NPM_VERSION=$("$NPM_BIN" --version 2>&1); then
    printf 'npm 无法运行：\n%s\n' "$NPM_VERSION" >&2
    exit 1
fi
printf '使用 npm: %s\n' "$NPM_VERSION"
printf 'npm 路径: %s\n' "$NPM_BIN"

if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x /opt/homebrew/bin/python3 ]; then
        PYTHON_BIN=/opt/homebrew/bin/python3
    elif [ -x /usr/local/bin/python3 ]; then
        PYTHON_BIN=/usr/local/bin/python3
    else
        PYTHON_BIN=python3
    fi
fi
printf '使用 Python: %s\n' "$PYTHON_BIN"
if ! PYTHON_VERSION=$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())' 2>&1); then
    printf 'Python 无法运行：\n%s\n' "$PYTHON_VERSION" >&2
    exit 1
fi
printf 'Python %s\n' "$PYTHON_VERSION"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    printf 'Python %s 不受支持，后端要求 Python 3.9+。请激活已有的 Python 3.9+ Conda 环境，或设置 PYTHON_BIN。\n' "$PYTHON_VERSION" >&2
    exit 1
fi

ENV_FILE="$ROOT_DIR/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    umask 077
    "$PYTHON_BIN" - <<'PY' > "$ENV_FILE"
import secrets

print(f"APP_SECRET={secrets.token_hex(32)}")
print(f"INITIAL_ADMIN_PASSWORD={secrets.token_urlsafe(18)}")
PY
    printf '已生成安全配置: %s\n' "$ENV_FILE"
    printf '初始管理员密码请查看该文件；后续安装不会覆盖。\n'
else
    printf '保留已有安全配置: %s\n' "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

PYPI_INDEX_URL=${PYPI_INDEX_URL:-http://mirrors.cloud.tencent.com/pypi/simple/}
trusted_host=${PYPI_INDEX_URL#*://}
trusted_host=${trusted_host%%/*}
PYPI_TRUSTED_HOST=${PYPI_TRUSTED_HOST:-$trusted_host}
printf '使用 PyPI: %s\n' "$PYPI_INDEX_URL"
printf '信任 PyPI 主机: %s\n' "$PYPI_TRUSTED_HOST"
"$PYTHON_BIN" -m pip install \
    --disable-pip-version-check \
    --only-binary greenlet \
    --index-url "$PYPI_INDEX_URL" \
    --trusted-host "$PYPI_TRUSTED_HOST" \
    -r "$ROOT_DIR/backend/requirements.txt"

"$NPM_BIN" --prefix "$ROOT_DIR/frontend" install
"$NPM_BIN" --prefix "$ROOT_DIR/frontend" run build

printf '%s\n' "安装完成。执行 sh scripts/start.sh 启动服务。"
