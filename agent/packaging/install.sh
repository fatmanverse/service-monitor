#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' '安装 Agent 需要 root 权限。' >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
SOURCE_DIR=${SOURCE_DIR:-$SCRIPT_DIR}
BIN_PATH=/usr/local/bin/service-monitor-agent
CONFIG_DIR=/etc/service-monitor-agent
STATE_DIR=/var/lib/service-monitor-agent
UNIT_PATH=/etc/systemd/system/service-monitor-agent.service
CA_FILE=${CA_FILE:-}
TLS_SERVER_NAME=${TLS_SERVER_NAME:-service-monitor-server}

# shellcheck source=scripts/platform.sh
. "$SCRIPT_DIR/platform.sh"

architecture=$(uname -m)
libc_version=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
artifact=$(select_artifact "$architecture" "$libc_version")
binary="$SOURCE_DIR/$artifact"
if [ ! -f "$binary" ]; then
    printf '找不到适配当前节点的 Agent 产物: %s\n' "$binary" >&2
    exit 1
fi
checksum_file="$binary.sha256"
if [ ! -f "$checksum_file" ]; then
    printf '缺少 Agent SHA-256 校验文件: %s\n' "$checksum_file" >&2
    exit 1
fi
if [ -n "$CA_FILE" ] && [ ! -f "$CA_FILE" ]; then
    printf 'Agent 公共 CA 文件不存在: %s\n' "$CA_FILE" >&2
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$SOURCE_DIR" && sha256sum -c "$artifact.sha256")
else
    expected=$(awk '{print $1}' "$checksum_file")
    actual=$(shasum -a 256 "$binary" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        printf '%s\n' 'Agent SHA-256 校验失败。' >&2
        exit 1
    fi
fi

install -d -m 0755 /usr/local/bin "$CONFIG_DIR"
install -d -m 0700 "$STATE_DIR"
install -m 0755 "$binary" "$BIN_PATH"
install -m 0644 "$SCRIPT_DIR/service-monitor-agent.service" "$UNIT_PATH"
if [ -n "$CA_FILE" ]; then
    install -m 0644 "$CA_FILE" "$CONFIG_DIR/ca.crt"
fi
if [ ! -f "$CONFIG_DIR/agent.toml" ]; then
    umask 077
    {
        printf '# Set the monitoring center TLS gRPC endpoint before starting the service.\n'
        printf 'center_url = "grpcs://monitor.example:50051"\n'
        if [ -n "$CA_FILE" ]; then
            printf 'ca_file = "%s/ca.crt"\n' "$CONFIG_DIR"
            printf 'tls_server_name = "%s"\n' "$TLS_SERVER_NAME"
        fi
        printf 'heartbeat_interval = 30\n'
        printf 'state_path = "%s/agent.db"\n' "$STATE_DIR"
    } > "$CONFIG_DIR/agent.toml"
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable service-monitor-agent.service
fi
printf 'Agent 已安装到 %s\n' "$BIN_PATH"
printf '配置文件: %s/agent.toml\n' "$CONFIG_DIR"
