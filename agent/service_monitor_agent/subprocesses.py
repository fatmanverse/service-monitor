"""Spawning external programs without leaking the frozen bundle's library path.

PyInstaller's onefile bootloader unpacks the bundle to a temporary directory and
prepends it to `LD_LIBRARY_PATH` so the frozen interpreter can find the bundled
`libpython` and `libcrypt`. That variable is inherited by every child process,
which makes programs like `systemctl` and `runuser` prefer our bundled copies
over the ones their own distribution shipped. Those copies are built against the
build image's glibc, not the target's, so a child needing a symbol version we do
not carry fails to load its libraries.

The bootloader saves the caller's original value in `LD_LIBRARY_PATH_ORIG`, so
restoring it -- or removing the variable when there was none -- gives children
the same environment they would have seen had the agent not been frozen.
"""

import os
import subprocess
import sys
from typing import Mapping, Optional


LIBRARY_PATH_VAR = "LD_LIBRARY_PATH"
BOOTLOADER_ORIGINAL_VAR = "LD_LIBRARY_PATH_ORIG"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle rather than a source tree."""
    return hasattr(sys, "_MEIPASS")


def system_environment(environ: Optional[Mapping[str, str]] = None) -> dict:
    """Returns a copy of `environ` with the bundle's library path undone.

    Outside a frozen bundle the environment is returned unchanged: there is no
    injected path to strip, and a `LD_LIBRARY_PATH` set by the operator is
    theirs to keep.
    """
    source = os.environ if environ is None else environ
    env = dict(source)
    if not is_frozen():
        return env

    original = env.pop(BOOTLOADER_ORIGINAL_VAR, None)
    if original:
        env[LIBRARY_PATH_VAR] = original
    else:
        # No original value means the bootloader created the variable itself.
        env.pop(LIBRARY_PATH_VAR, None)
    return env


def run(argv: list, **kwargs):
    """`subprocess.run` with the target system's own library search path.

    An explicit `env` is passed through untouched so callers stay in control.
    """
    kwargs.setdefault("env", system_environment())
    return subprocess.run(argv, **kwargs)
