import pytest

from app.start_commands import (
    build_agent_start_argv,
    build_ssh_start_command,
    validate_start_user,
)


def test_empty_start_user_keeps_current_execution_user():
    command = "systemctl start api-service"

    assert build_ssh_start_command(command, None) == command
    assert build_agent_start_argv(command, None) == ["/bin/sh", "-lc", command]


def test_configured_start_user_uses_non_interactive_user_switch():
    command = "cd /srv/api && ./start.sh"

    assert build_ssh_start_command(command, "service-user") == (
        "sudo -n -u service-user -- /bin/sh -lc 'cd /srv/api && ./start.sh'"
    )
    assert build_agent_start_argv(command, "service-user") == [
        "runuser",
        "--user",
        "service-user",
        "--",
        "/bin/sh",
        "-lc",
        command,
    ]


@pytest.mark.parametrize(
    "value",
    ["root; reboot", "../../root", "user name", "UPPERCASE", ""],
)
def test_invalid_start_user_is_rejected(value):
    with pytest.raises(ValueError, match="启动用户格式无效"):
        validate_start_user(value)
