#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' '卸载 Agent 需要 root 权限。' >&2
    exit 1
fi

BIN_PATH=/usr/local/bin/service-monitor-agent
CONFIG_DIR=/etc/service-monitor-agent
STATE_DIR=/var/lib/service-monitor-agent
UNIT_PATH=/etc/systemd/system/service-monitor-agent.service

if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now service-monitor-agent.service 2>/dev/null || true
fi
rm -f "$BIN_PATH" "$UNIT_PATH"
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
fi

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$CONFIG_DIR" "$STATE_DIR"
    printf '%s\n' 'Agent、配置和状态库已删除。'
else
    printf '%s\n' 'Agent 已卸载；配置和状态库已保留。使用 --purge 显式删除。'
fi
