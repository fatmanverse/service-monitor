import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from service_monitor_agent.probes import parse_systemd_unit, probe_process


class ProbeTests(unittest.TestCase):
    def test_systemd_pattern_is_strict_and_uses_exit_code(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0)

        result = probe_process(
            {"key": "process", "process_pattern": "systemctl status nginx", "timeout_seconds": 5},
            runner=runner,
        )
        self.assertTrue(result.success)
        self.assertEqual(calls[0], ["systemctl", "is-active", "--quiet", "--", "nginx"])
        self.assertIsNone(parse_systemd_unit("systemctl status 'bad; reboot'"))

    def test_proc_cmdline_substring_match(self):
        with tempfile.TemporaryDirectory() as tempdir:
            process = Path(tempdir) / "4242"
            process.mkdir()
            (process / "cmdline").write_bytes(b"python\x00/opt/app/server.py\x00")
            result = probe_process(
                {"key": "process", "process_pattern": "/opt/app/server.py", "timeout_seconds": 5},
                proc_root=tempdir,
            )
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
