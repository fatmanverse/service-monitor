import unittest
from types import SimpleNamespace

from service_monitor_agent.engine import AgentEngine
from service_monitor_agent.probes import ProbeResult


class FakeStorage:
    def __init__(self):
        self.reports = []
        self.commands = {}

    def enqueue_report(self, report):
        report = {**report, "report_id": str(len(self.reports) + 1), "report_sequence": len(self.reports) + 1}
        self.reports.append(report)
        return report

    def command_result(self, command_id):
        return self.commands.get(command_id)

    def save_command_result(self, command_id, result):
        self.commands.setdefault(command_id, result)


class EngineTests(unittest.TestCase):
    def service(self):
        return {
            "id": 7,
            "probes": [
                {"key": "process"},
                {"key": "http"},
            ],
            "health_rule": {
                "op": "AND",
                "children": [
                    {"probe": "process"},
                    {"probe": "http"},
                ],
            },
            "auto_restart": True,
            "start_command": "start-app",
            "start_user": None,
        }

    def test_failed_rule_restarts_then_rechecks(self):
        attempts = {"process": 0, "http": 0}

        def probe_runner(probe):
            attempts[probe["key"]] += 1
            success = attempts[probe["key"]] > 1
            return ProbeResult(probe["key"], success, "ok" if success else "down")

        storage = FakeStorage()
        engine = AgentEngine(
            storage,
            probe_runner=probe_runner,
            start_runner=lambda service: SimpleNamespace(success=True, message="started"),
        )
        report = engine.check_service(self.service())
        self.assertTrue(report["success"])
        self.assertTrue(report["restarted"])
        self.assertEqual(attempts, {"process": 2, "http": 2})

    def test_command_id_is_idempotent(self):
        storage = FakeStorage()
        engine = AgentEngine(
            storage,
            probe_runner=lambda probe: ProbeResult(probe["key"], True, "ok"),
        )
        command = {"command_id": "cmd-1", "service_id": 7, "command_type": "probe_service"}
        first = engine.execute_command(command, {7: self.service()})
        second = engine.execute_command(command, {7: self.service()})
        self.assertIs(first, second)
        self.assertEqual(len(storage.reports), 1)


if __name__ == "__main__":
    unittest.main()
