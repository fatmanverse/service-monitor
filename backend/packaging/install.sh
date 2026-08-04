#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' '安装服务监控需要 root 权限。' >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
artifact=${1:-}
if [ -z "$artifact" ] || [ ! -f "$SCRIPT_DIR/$artifact" ]; then
    printf '用法: %s <server-binary-name>\n' "$0" >&2
    exit 1
fi
if [ ! -f "$SCRIPT_DIR/$artifact.sha256" ]; then
    printf '缺少校验文件: %s.sha256\n' "$artifact" >&2
    exit 1
fi
(cd "$SCRIPT_DIR" && sha256sum -c "$artifact.sha256")

install -d -m 0755 /usr/local/bin /etc/service-monitor
install -d -m 0700 /var/lib/service-monitor
install -m 0755 "$SCRIPT_DIR/$artifact" /usr/local/bin/service-monitor-server
install -m 0644 "$SCRIPT_DIR/service-monitor-backend.service" /etc/systemd/system/service-monitor-backend.service
if [ ! -f /etc/service-monitor/service-monitor.env ]; then
    install -m 0600 "$SCRIPT_DIR/service-monitor.env.example" /etc/service-monitor/service-monitor.env
fi
systemctl daemon-reload
systemctl enable service-monitor-backend.service
printf '%s\n' '服务监控已安装。请修改 /etc/service-monitor/service-monitor.env 后启动服务。'
