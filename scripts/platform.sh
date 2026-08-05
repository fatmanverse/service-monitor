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

validate_product() {
    case "$1" in
        agent|server) return ;;
        *)
            printf '不支持的产品类型: %s\n' "$1" >&2
            return 1
            ;;
    esac
}

select_artifact_for() {
    product=$1
    validate_product "$product" || return 1
    arch=$(normalize_architecture "$2") || return 1
    libc_target=$(glibc_minor_target "$3") || return 1
    printf 'service-monitor-%s-linux-%s-glibc%s\n' "$product" "$arch" "$libc_target"
}

select_artifact() {
    select_artifact_for agent "$1" "$2"
}

artifact_is_compatible() {
    product=$1
    artifact=$2
    validate_product "$product" || return 1
    host_arch=$(normalize_architecture "$3") || return 1
    host_libc_target=$(glibc_minor_target "$4") || return 1
    prefix=service-monitor-$product-linux-

    case "$artifact" in
        "${prefix}x86_64-glibc217") artifact_arch=x86_64; artifact_libc_target=217 ;;
        "${prefix}x86_64-glibc228") artifact_arch=x86_64; artifact_libc_target=228 ;;
        "${prefix}arm64-glibc217") artifact_arch=arm64; artifact_libc_target=217 ;;
        "${prefix}arm64-glibc228") artifact_arch=arm64; artifact_libc_target=228 ;;
        *)
            printf '无法识别的 %s 产物名称: %s\n' "$product" "$artifact" >&2
            return 1
            ;;
    esac

    if [ "$artifact_arch" != "$host_arch" ]; then
        printf '产物架构与当前主机不匹配: 产物为 %s，主机为 %s\n' "$artifact_arch" "$host_arch" >&2
        return 1
    fi
    if [ "$artifact_libc_target" -gt "$host_libc_target" ]; then
        printf '产物 glibc 基线高于当前主机: 产物为 2.%s，主机仅支持 2.%s\n' "$artifact_libc_target" "$host_libc_target" >&2
        return 1
    fi
}

if [ "${0##*/}" = "platform.sh" ] && [ "$#" -gt 0 ]; then
    select_artifact "$@"
fi
