#!/bin/sh
set -eu

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

find_linked_libcrypt() {
    binary=$1
    if ! command -v ldd >/dev/null 2>&1; then
        printf '%s\n' '无法检查 PyInstaller 运行库：系统缺少 ldd。' >&2
        return 2
    fi
    if ! dependencies=$(ldd "$binary" 2>&1); then
        printf '无法读取共享库依赖: %s\n%s\n' "$binary" "$dependencies" >&2
        return 2
    fi
    library=$(printf '%s\n' "$dependencies" | awk '
        $1 ~ /^libcrypt\.so\.[0-9]+$/ && $2 == "=>" { print $3; exit }
        $1 ~ /^\// && $1 ~ /\/libcrypt\.so\.[0-9]+$/ { print $1; exit }
    ')
    if [ -z "$library" ]; then
        return 1
    fi
    if [ ! -f "$library" ]; then
        printf 'libpython 需要的 libcrypt 不存在: %s\n' "$library" >&2
        return 2
    fi
    printf '%s\n' "$library"
}

find_python_libcrypt_dependencies() {
    libpython=$1
    dynload_dir=$2
    libraries=
    for binary in "$libpython" "$dynload_dir"/*.so; do
        if [ ! -f "$binary" ]; then
            continue
        fi
        if library=$(find_linked_libcrypt "$binary"); then
            case "|$libraries|" in
                *"|$library|"*) ;;
                *) libraries=${libraries:+"$libraries|"}$library ;;
            esac
        else
            status=$?
            if [ "$status" -ne 1 ]; then
                return "$status"
            fi
        fi
    done
    if [ -n "$libraries" ]; then
        printf '%s\n' "$libraries" | tr '|' '\n'
    fi
}
