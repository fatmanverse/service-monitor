import base64
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SYSTEMD_UNIT_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@_.:-"
)


@dataclass(frozen=True)
class ProbeResult:
    key: str
    success: bool
    message: str
    response_ms: Optional[int] = None


def parse_systemd_unit(pattern: str) -> Optional[str]:
    try:
        parts = shlex.split(pattern.strip())
    except ValueError:
        return None
    if len(parts) != 3 or parts[0] != "systemctl":
        return None
    if parts[1] not in {"status", "is-active"}:
        return None
    unit = parts[2]
    if not unit or any(char not in SYSTEMD_UNIT_CHARS for char in unit):
        return None
    return unit


def probe_process(
    probe: dict,
    proc_root: str = "/proc",
    runner: Callable = subprocess.run,
) -> ProbeResult:
    key = probe["key"]
    pattern = probe.get("process_pattern") or ""
    started = time.monotonic()
    systemd_unit = parse_systemd_unit(pattern)
    if systemd_unit:
        try:
            completed = runner(
                ["systemctl", "is-active", "--quiet", "--", systemd_unit],
                check=False,
                timeout=probe["timeout_seconds"],
            )
            elapsed = int((time.monotonic() - started) * 1000)
            if completed.returncode == 0:
                return ProbeResult(key, True, f"systemd 服务 {systemd_unit} 在线", elapsed)
            return ProbeResult(key, False, f"systemd 服务 {systemd_unit} 未运行", elapsed)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProbeResult(
                key, False, str(exc), int((time.monotonic() - started) * 1000)
            )

    pattern_bytes = pattern.encode()
    try:
        entries = Path(proc_root).iterdir()
    except OSError as exc:
        return ProbeResult(key, False, str(exc), int((time.monotonic() - started) * 1000))
    for entry in entries:
        if not entry.name.isdigit() or entry.name == str(os.getpid()):
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if pattern_bytes in cmdline:
            return ProbeResult(
                key, True, "进程存在", int((time.monotonic() - started) * 1000)
            )
    return ProbeResult(
        key, False, "未找到匹配进程", int((time.monotonic() - started) * 1000)
    )


def probe_http(probe: dict, opener: Callable = urlopen) -> ProbeResult:
    key = probe["key"]
    headers = dict(probe.get("headers") or {})
    auth_type = probe.get("auth_type", "none")
    if auth_type == "basic":
        raw = f"{probe.get('auth_username') or ''}:{probe.get('auth_secret') or ''}"
        token = base64.b64encode(raw.encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif auth_type == "bearer":
        headers["Authorization"] = f"Bearer {probe.get('auth_secret') or ''}"
    method = probe["probe_type"].upper()
    data = None
    if method == "POST" and probe.get("body") is not None:
        import json

        data = json.dumps(probe["body"], ensure_ascii=False).encode()
        headers.setdefault("Content-Type", "application/json")
    request = Request(probe["url"], data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with opener(request, timeout=probe["timeout_seconds"]) as response:
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, OSError, TimeoutError) as exc:
        return ProbeResult(key, False, str(exc), int((time.monotonic() - started) * 1000))
    elapsed = int((time.monotonic() - started) * 1000)
    expected = probe["expected_status"]
    if status == expected:
        return ProbeResult(key, True, f"HTTP {status}", elapsed)
    return ProbeResult(key, False, f"期望 HTTP {expected}，实际 {status}", elapsed)


def run_probe(probe: dict) -> ProbeResult:
    if probe["probe_type"] == "process":
        return probe_process(probe)
    return probe_http(probe)
