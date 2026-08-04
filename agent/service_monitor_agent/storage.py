import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .crypto import local_cipher


class AgentStorage:
    def __init__(self, path: str, outbox_limit: int = 10000, outbox_days: int = 7):
        self.path = Path(path)
        self.outbox_limit = outbox_limit
        self.outbox_days = outbox_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        os.chmod(self.path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS config_cache (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                revision INTEGER NOT NULL,
                encrypted_payload BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outbox (
                report_id TEXT PRIMARY KEY,
                report_sequence INTEGER NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS executed_commands (
                command_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, key: str) -> Optional[str]:
        row = self.db.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.db.commit()

    def ensure_identity(self) -> tuple:
        agent_uuid = self.get("agent_uuid")
        claim_token = self.get("claim_token")
        if not agent_uuid:
            agent_uuid = str(uuid4())
            self.set("agent_uuid", agent_uuid)
        if not claim_token and not self.get("agent_secret"):
            import secrets

            claim_token = secrets.token_urlsafe(32)
            self.set("claim_token", claim_token)
        return agent_uuid, claim_token

    def save_secret(self, secret: str) -> None:
        self.set("agent_secret", secret)
        self.db.execute("DELETE FROM metadata WHERE key = 'claim_token'")
        self.db.commit()

    def save_config(self, payload: dict, secret: str) -> bool:
        revision = int(payload["config_revision"])
        if revision <= self.config_revision():
            return False
        encrypted = local_cipher(secret).encrypt(
            json.dumps(payload, ensure_ascii=False).encode()
        )
        with self.db:
            self.db.execute(
                "INSERT INTO config_cache(id, revision, encrypted_payload) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, "
                "encrypted_payload=excluded.encrypted_payload",
                (revision, encrypted),
            )
        return True

    def load_config(self, secret: str) -> Optional[dict]:
        row = self.db.execute(
            "SELECT encrypted_payload FROM config_cache WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        return json.loads(local_cipher(secret).decrypt(row[0]).decode())

    def config_revision(self) -> int:
        row = self.db.execute("SELECT revision FROM config_cache WHERE id = 1").fetchone()
        return row[0] if row else 0

    def enqueue_report(self, payload: dict) -> dict:
        report_id = str(uuid4())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT value FROM metadata WHERE key = 'report_sequence'"
            ).fetchone()
            sequence = int(row[0]) + 1 if row else 1
            payload = {**payload, "report_id": report_id, "report_sequence": sequence}
            self.db.execute(
                "INSERT INTO outbox VALUES (?, ?, ?, ?)",
                (report_id, sequence, json.dumps(payload), payload["occurred_at"]),
            )
            self.db.execute(
                "INSERT INTO metadata(key, value) VALUES ('report_sequence', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(sequence),),
            )
            self._prune_outbox(datetime.now(timezone.utc))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return payload

    def _prune_outbox(self, now: datetime) -> None:
        cutoff = (now - timedelta(days=self.outbox_days)).isoformat()
        self.db.execute("DELETE FROM outbox WHERE occurred_at < ?", (cutoff,))
        excess = self.db.execute(
            "SELECT MAX(COUNT(*) - ?, 0) FROM outbox", (self.outbox_limit,)
        ).fetchone()[0]
        if excess:
            self.db.execute(
                "DELETE FROM outbox WHERE report_id IN ("
                "SELECT report_id FROM outbox ORDER BY report_sequence LIMIT ?"
                ")",
                (excess,),
            )

    def pending_reports(self, limit: int = 500) -> list:
        rows = self.db.execute(
            "SELECT payload_json FROM outbox ORDER BY report_sequence LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def acknowledge_reports(self, report_ids: list) -> None:
        self.db.executemany(
            "DELETE FROM outbox WHERE report_id = ?",
            [(report_id,) for report_id in report_ids],
        )
        self.db.commit()

    def command_result(self, command_id: str) -> Optional[dict]:
        row = self.db.execute(
            "SELECT result_json FROM executed_commands WHERE command_id = ?",
            (command_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_command_result(self, command_id: str, result: dict) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO executed_commands VALUES (?, ?)",
            (command_id, json.dumps(result)),
        )
        self.db.commit()
