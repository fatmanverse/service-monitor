#!/bin/sh
set -eu

PYTHON_VERSION=${PYTHON_VERSION:-3.9.23}
PYTHON_PREFIX=${PYTHON_PREFIX:-/opt/service-monitor-python}
PYTHON_TARBALL_SHA256=${PYTHON_TARBALL_SHA256:-9a69aad184dc1d06f6819930741da3a328d34875a41f8ba33875774dbfc51b51}
SOURCE_DIR=/tmp/service-monitor-python-source
TARBALL=/tmp/Python-$PYTHON_VERSION.tgz

if [ -x "$PYTHON_PREFIX/bin/python3" ] && "$PYTHON_PREFIX/bin/python3" -c 'import sysconfig; raise SystemExit(0 if sysconfig.get_config_var("Py_ENABLE_SHARED") else 1)'; then
    printf '%s\n' "$PYTHON_PREFIX/bin/python3"
    exit 0
fi

rm -rf "$SOURCE_DIR"
mkdir -p "$SOURCE_DIR"
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

LD_LIBRARY_PATH="$PYTHON_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    "$PYTHON_PREFIX/bin/python3" -c 'import bz2, ctypes, lzma, sqlite3, ssl, sysconfig; assert sysconfig.get_config_var("Py_ENABLE_SHARED") == 1'
printf '%s\n' "$PYTHON_PREFIX/bin/python3"
