#!/bin/sh
set -eu

PYTHON_VERSION=${PYTHON_VERSION:-3.9.23}
PYTHON_PREFIX=${PYTHON_PREFIX:-/opt/service-monitor-python}
PYTHON_TARBALL_SHA256=${PYTHON_TARBALL_SHA256:-9a69aad184dc1d06f6819930741da3a328d34875a41f8ba33875774dbfc51b51}
SOURCE_DIR=/tmp/service-monitor-python-source
TARBALL=/tmp/Python-$PYTHON_VERSION.tgz

install_build_dependencies() {
    set -- bzip2-devel libffi-devel openssl-devel readline-devel sqlite-devel xz-devel zlib-devel
    if command -v dnf >/dev/null 2>&1; then
        dnf install -y "$@" >&2
        dnf clean all >&2
        return
    fi
    if command -v yum >/dev/null 2>&1; then
        yum install -y "$@" >&2
        yum clean all >&2
        return
    fi
    printf '%s\n' 'No supported package manager found for CPython build dependencies.' >&2
    exit 1
}

python_is_usable() {
    LD_LIBRARY_PATH="$PYTHON_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        "$PYTHON_PREFIX/bin/python3" -c 'import bz2, ctypes, lzma, sqlite3, ssl, sysconfig; assert sysconfig.get_config_var("Py_ENABLE_SHARED") == 1'
}

if [ -x "$PYTHON_PREFIX/bin/python3" ] && python_is_usable; then
    printf '%s\n' "$PYTHON_PREFIX/bin/python3"
    exit 0
fi

rm -rf "$SOURCE_DIR" "$PYTHON_PREFIX"
mkdir -p "$SOURCE_DIR"
install_build_dependencies
curl -fsSL "https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz" -o "$TARBALL"
printf '%s  %s\n' "$PYTHON_TARBALL_SHA256" "$TARBALL" | sha256sum -c - >&2
tar -xzf "$TARBALL" -C "$SOURCE_DIR" --strip-components=1

cd "$SOURCE_DIR"
./configure \
    --prefix="$PYTHON_PREFIX" \
    --enable-shared \
    --with-ensurepip=install >&2
make -j"$(getconf _NPROCESSORS_ONLN)" >&2
make install >&2

python_is_usable
printf '%s\n' "$PYTHON_PREFIX/bin/python3"
