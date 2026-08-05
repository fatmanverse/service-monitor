#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' '安装服务监控需要 root 权限。' >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/platform.sh
. "$SCRIPT_DIR/platform.sh"

artifact=${1:-}
if [ -z "$artifact" ] || [ ! -f "$SCRIPT_DIR/$artifact" ]; then
    printf '用法: %s <server-binary-name>\n' "$0" >&2
    exit 1
fi
architecture=$(uname -m)
libc_version=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
artifact_is_compatible server "$artifact" "$architecture" "$libc_version"
if [ ! -f "$SCRIPT_DIR/$artifact.sha256" ]; then
    printf '缺少校验文件: %s.sha256\n' "$artifact" >&2
    exit 1
fi
(cd "$SCRIPT_DIR" && sha256sum -c "$artifact.sha256")

install -d -m 0755 /usr/local/bin /etc/service-monitor
install -d -m 0700 /var/lib/service-monitor
temporary_binary=/usr/local/bin/.service-monitor-server.install.$$
cleanup() {
    rm -f "$temporary_binary"
}
trap cleanup 0 1 2 15
install -m 0755 "$SCRIPT_DIR/$artifact" "$temporary_binary"
if ! "$temporary_binary" --self-test; then
    printf '%s\n' 'Server 二进制自检失败，未替换已安装版本。' >&2
    exit 1
fi
mv -f "$temporary_binary" /usr/local/bin/service-monitor-server
trap - 0 1 2 15
install -m 0644 "$SCRIPT_DIR/service-monitor-backend.service" /etc/systemd/system/service-monitor-backend.service
if [ ! -f /etc/service-monitor/service-monitor.env ]; then
    install -m 0600 "$SCRIPT_DIR/service-monitor.env.example" /etc/service-monitor/service-monitor.env
fi
systemctl daemon-reload
systemctl enable service-monitor-backend.service
printf '%s\n' '服务监控已安装。请修改 /etc/service-monitor/service-monitor.env 后启动服务。'
