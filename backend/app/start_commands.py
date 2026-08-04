import re
import shlex
from typing import List, Optional


START_USER_PATTERN = re.compile(r"^[a-z_][a-z0-9_.-]{0,98}\$?$")


def validate_start_user(start_user: Optional[str]) -> None:
    if start_user is None:
        return
    if not START_USER_PATTERN.fullmatch(start_user):
        raise ValueError("启动用户格式无效")


def build_ssh_start_command(start_command: str, start_user: Optional[str]) -> str:
    if start_user is None:
        return start_command
    validate_start_user(start_user)
    return (
        f"sudo -n -u {shlex.quote(start_user)} -- /bin/sh -lc "
        f"{shlex.quote(start_command)}"
    )


def build_agent_start_argv(start_command: str, start_user: Optional[str]) -> List[str]:
    if start_user is None:
        return ["/bin/sh", "-lc", start_command]
    validate_start_user(start_user)
    return [
        "runuser",
        "--user",
        start_user,
        "--",
        "/bin/sh",
        "-lc",
        start_command,
    ]
