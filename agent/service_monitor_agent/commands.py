import pwd
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str
    response_ms: Optional[int] = None


def build_start_argv(start_command: str, start_user: Optional[str]) -> list:
    if not start_user:
        return ["/bin/sh", "-lc", start_command]
    pwd.getpwnam(start_user)
    return [
        "runuser",
        "--user",
        start_user,
        "--",
        "/bin/sh",
        "-lc",
        start_command,
    ]


def execute_start_command(
    service: dict,
    runner: Callable = subprocess.run,
    timeout_seconds: int = 30,
) -> CommandResult:
    start_command = service.get("start_command")
    if not start_command:
        return CommandResult(False, "未配置启动命令")
    started = time.monotonic()
    try:
        argv = build_start_argv(start_command, service.get("start_user"))
        completed = runner(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except KeyError:
        return CommandResult(False, f"启动用户不存在：{service.get('start_user')}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(False, str(exc), int((time.monotonic() - started) * 1000))
    elapsed = int((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        message = (completed.stderr or "").strip() or f"启动命令退出码 {completed.returncode}"
        return CommandResult(False, message, elapsed)
    return CommandResult(True, "启动命令执行成功", elapsed)
