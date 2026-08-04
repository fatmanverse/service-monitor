import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from service_monitor_agent.storage import AgentStorage


class AgentStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = AgentStorage(str(Path(self.tempdir.name) / "agent.db"), outbox_limit=2)

    def tearDown(self):
        self.storage.close()
        self.tempdir.cleanup()

    def test_config_only_accepts_newer_revision_and_is_encrypted(self):
        self.assertTrue(self.storage.save_config({"config_revision": 2, "secret": "token"}, "agent-secret"))
        self.assertFalse(self.storage.save_config({"config_revision": 1}, "agent-secret"))
        self.assertEqual(self.storage.load_config("agent-secret")["secret"], "token")
        raw = self.storage.path.read_bytes()
        self.assertNotIn(b"token", raw)

    def test_sequence_persists_and_outbox_prunes_oldest(self):
        now = datetime.now(timezone.utc)
        for offset in range(3):
            report = self.storage.enqueue_report(
                {"occurred_at": (now + timedelta(seconds=offset)).isoformat()}
            )
        self.assertEqual(report["report_sequence"], 3)
        self.assertEqual(
            [item["report_sequence"] for item in self.storage.pending_reports()], [2, 3]
        )


if __name__ == "__main__":
    unittest.main()
