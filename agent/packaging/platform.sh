#!/bin/sh
set -eu

normalize_architecture() {
    case "$1" in
        x86_64|amd64) printf '%s\n' x86_64 ;;
        aarch64|arm64) printf '%s\n' arm64 ;;
        *)
            printf '不支持的 CPU 架构: %s\n' "$1" >&2
            return 1
            ;;
    esac
}

glibc_minor_target() {
    version=$1
    case "$version" in
        musl*|*musl*|''|*[!0-9.]*|*.*.*)
            printf '无法识别或不支持的 libc 版本: %s\n' "$version" >&2
            return 1
            ;;
    esac
    major=${version%%.*}
    minor=${version#*.}
    if [ "$major" -ne 2 ] 2>/dev/null; then
        printf '仅支持 glibc 2.17 或更高版本，当前为: %s\n' "$version" >&2
        return 1
    fi
    case "$minor" in
        ''|*[!0-9]*)
            printf '无法识别 glibc 版本: %s\n' "$version" >&2
            return 1
            ;;
    esac
    if [ "$minor" -lt 17 ]; then
        printf 'glibc 低于 2.17，不支持: %s\n' "$version" >&2
        return 1
    fi
    if [ "$minor" -ge 28 ]; then
        printf '%s\n' 228
    else
        printf '%s\n' 217
    fi
}

select_artifact() {
    arch=$(normalize_architecture "$1") || return 1
    libc_target=$(glibc_minor_target "$2") || return 1
    printf 'service-monitor-agent-linux-%s-glibc%s\n' "$arch" "$libc_target"
}

if [ "${0##*/}" = "platform.sh" ] && [ "$#" -gt 0 ]; then
    select_artifact "$@"
fi
