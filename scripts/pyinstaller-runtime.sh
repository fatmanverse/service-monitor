#!/bin/sh
set -eu

libcrypt_bundle_required() {
    case "$1" in
        *-glibc217) return 0 ;;
        *) return 1 ;;
    esac
}

find_runtime_library() {
    library=$1

    if [ -z "${RUNTIME_LIBRARY_DIRS:-}" ] && command -v ldconfig >/dev/null 2>&1; then
        candidate=$(ldconfig -p 2>/dev/null | awk -v library="$library" '$1 == library { print $NF; exit }')
        if [ -n "$candidate" ] && [ -e "$candidate" ]; then
            printf '%s\n' "$candidate"
            return
        fi
    fi

    directories=${RUNTIME_LIBRARY_DIRS:-/lib64:/usr/lib64:/lib:/usr/lib}
    old_ifs=$IFS
    IFS=:
    for directory in $directories; do
        if [ -e "$directory/$library" ]; then
            IFS=$old_ifs
            printf '%s\n' "$directory/$library"
            return
        fi
    done
    IFS=$old_ifs

    printf '找不到 PyInstaller 运行库: %s\n' "$library" >&2
    return 1
}
