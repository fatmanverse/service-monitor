#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/platform.sh
. "$SCRIPT_DIR/platform.sh"

architecture=$(normalize_architecture "$(uname -m)")
libc_version=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
libc_target=$(glibc_minor_target "$libc_version")

binary=
if [ "$libc_target" = 228 ]; then
    candidates="service-monitor-server-linux-$architecture-glibc228 service-monitor-server-linux-$architecture-glibc217"
else
    candidates="service-monitor-server-linux-$architecture-glibc217"
fi
for candidate in $candidates; do
    if [ -f "$SCRIPT_DIR/$candidate" ]; then
        binary=$SCRIPT_DIR/$candidate
        artifact=$candidate
        break
    fi
done
if [ -z "$binary" ]; then
    printf '当前目录没有适配 %s / glibc %s 的 Server 二进制。\n' \
        "$architecture" "$libc_version" >&2
    exit 1
fi
artifact_is_compatible server "$artifact" "$architecture" "$libc_version"

checksum_file=$binary.sha256
if [ ! -f "$checksum_file" ]; then
    printf '缺少校验文件: %s\n' "$checksum_file" >&2
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$SCRIPT_DIR" && sha256sum -c "$artifact.sha256")
else
    expected=$(awk '{print $1}' "$checksum_file")
    actual=$(shasum -a 256 "$binary" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        printf '%s\n' 'Server SHA-256 校验失败。' >&2
        exit 1
    fi
fi
if ! "$binary" --self-test; then
    printf '%s\n' 'Server 二进制自检失败。' >&2
    exit 1
fi

ENV_FILE=$SCRIPT_DIR/.service-monitor.env
DATA_DIR=$SCRIPT_DIR/data
CERT_DIR=$SCRIPT_DIR/certs
created_env=false
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$DATA_DIR/service_monitor.db" ]; then
        printf '%s\n' '检测到已有数据库但缺少 .service-monitor.env，为避免密钥错配已停止启动。' >&2
        exit 1
    fi
    umask 077
    mkdir -p "$DATA_DIR" "$CERT_DIR"
    chmod 700 "$DATA_DIR" "$CERT_DIR"
    app_secret=$(od -An -N 32 -tx1 /dev/urandom | tr -d ' \n')
    admin_password=$(od -An -N 18 -tx1 /dev/urandom | tr -d ' \n')
    {
        printf 'APP_SECRET=%s\n' "$app_secret"
        printf 'INITIAL_ADMIN_USERNAME=admin\n'
        printf 'INITIAL_ADMIN_PASSWORD=%s\n' "$admin_password"
        printf 'DATABASE_URL=sqlite:///./data/service_monitor.db\n'
        printf 'HOST=0.0.0.0\n'
        printf 'PORT=8000\n'
        printf 'SCHEDULER_ENABLED=true\n'
        printf 'AGENT_GRPC_ENABLED=true\n'
        printf 'AGENT_GRPC_BIND=[::]:50051\n'
        printf 'AGENT_GRPC_CERT_DIR=./certs\n'
        printf 'AGENT_GRPC_TLS_SERVER_NAME=service-monitor-server\n'
    } > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    created_env=true
else
    mkdir -p "$DATA_DIR" "$CERT_DIR"
    chmod 700 "$DATA_DIR" "$CERT_DIR"
fi

override_port=${PORT:-}
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
if [ -n "$override_port" ]; then
    PORT=$override_port
    export PORT
fi

if [ "$created_env" = true ]; then
    printf '\n首次初始化完成。\n'
    printf '访问地址: http://127.0.0.1:%s\n' "$PORT"
    printf '管理员账号: %s\n' "$INITIAL_ADMIN_USERNAME"
    printf '管理员密码: %s\n\n' "$INITIAL_ADMIN_PASSWORD"
else
    printf '使用已有配置启动: http://127.0.0.1:%s\n' "$PORT"
fi

cd "$SCRIPT_DIR"
exec "$binary"
