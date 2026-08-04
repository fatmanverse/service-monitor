import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from service_monitor_agent.runtime import AgentRuntime
from service_monitor_agent.storage import AgentStorage


class FakeClient:
    def __init__(self):
        self.uploaded = []

    def heartbeat(self, agent_uuid, agent_secret, config_revision, outbox_size):
        return {
            "protocol_version": 1,
            "config_revision": 1,
            "config_changed": config_revision < 1,
            "commands": [],
        }

    def fetch_config(self, agent_uuid, agent_secret):
        return {
            "protocol_version": 1,
            "config_revision": 1,
            "host_id": 1,
            "services": [],
        }

    def upload_reports(self, agent_uuid, agent_secret, reports):
        self.uploaded.extend(reports)
        return {"protocol_version": 1, "accepted": len(reports), "duplicates": 0}


class RuntimeTests(unittest.TestCase):
    def test_successful_upload_removes_outbox(self):
        with tempfile.TemporaryDirectory() as tempdir:
            storage = AgentStorage(str(Path(tempdir) / "agent.db"))
            storage.set("agent_uuid", "agent-uuid-123456")
            storage.save_secret("secret")
            storage.enqueue_report(
                {
                    "service_id": 1,
                    "success": True,
                    "message": "ok",
                    "occurred_at": "2026-08-04T00:00:00+00:00",
                    "probes": [],
                }
            )
            client = FakeClient()
            runtime = AgentRuntime(SimpleNamespace(heartbeat_interval=30), storage, client)
            runtime.sync_once()
            self.assertEqual(len(client.uploaded), 1)
            self.assertEqual(storage.pending_reports(), [])
            storage.close()


if __name__ == "__main__":
    unittest.main()
