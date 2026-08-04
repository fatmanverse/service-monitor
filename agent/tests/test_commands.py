import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service_monitor_agent.commands import build_start_argv, execute_start_command


class CommandTests(unittest.TestCase):
    def test_empty_user_does_not_switch_user(self):
        self.assertEqual(build_start_argv("echo ok", None), ["/bin/sh", "-lc", "echo ok"])

    @patch("service_monitor_agent.commands.pwd.getpwnam")
    def test_selected_user_uses_runuser_argv(self, getpwnam):
        getpwnam.return_value = object()
        self.assertEqual(
            build_start_argv("systemctl start demo", "deploy"),
            ["runuser", "--user", "deploy", "--", "/bin/sh", "-lc", "systemctl start demo"],
        )

    def test_nonzero_exit_is_explicit_failure(self):
        result = execute_start_command(
            {"start_command": "false", "start_user": None},
            runner=lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="denied"),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.message, "denied")


if __name__ == "__main__":
    unittest.main()
