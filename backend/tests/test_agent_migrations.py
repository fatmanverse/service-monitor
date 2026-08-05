import sqlite3

from sqlalchemy import inspect, text

from app.database import Database
from app.migrations import migrate_database
from app.models import Agent, AgentCommand, AgentReportReceipt, Host, ProbeLog, Service


def create_pre_agent_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE hosts (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            hostname VARCHAR(255) NOT NULL,
            port INTEGER NOT NULL DEFAULT 22,
            username VARCHAR(100) NOT NULL,
            auth_type VARCHAR(16) NOT NULL DEFAULT 'password',
            password_encrypted TEXT,
            private_key_path VARCHAR(500),
            check_interval INTEGER NOT NULL DEFAULT 60,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            status VARCHAR(16) NOT NULL DEFAULT 'unknown',
            last_checked_at DATETIME,
            last_error TEXT,
            next_check_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE UNIQUE INDEX ix_hosts_name ON hosts (name);
        CREATE INDEX ix_hosts_next_check_at ON hosts (next_check_at);

        CREATE TABLE resource_groups (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR(500),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );

        CREATE TABLE services (
            id INTEGER PRIMARY KEY,
            host_id INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
            resource_group_id INTEGER REFERENCES resource_groups(id) ON DELETE RESTRICT,
            name VARCHAR(100) NOT NULL,
            health_rule_json TEXT,
            probe_type VARCHAR(16) NOT NULL,
            process_pattern VARCHAR(500),
            url VARCHAR(1000),
            headers_json TEXT NOT NULL DEFAULT '{}',
            body_json TEXT,
            auth_type VARCHAR(16) NOT NULL DEFAULT 'none',
            auth_username VARCHAR(255),
            auth_secret_encrypted TEXT,
            expected_status INTEGER NOT NULL DEFAULT 200,
            timeout_seconds INTEGER NOT NULL DEFAULT 10,
            start_command TEXT,
            check_interval INTEGER NOT NULL DEFAULT 60,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            auto_restart BOOLEAN NOT NULL DEFAULT 0,
            alert_enabled BOOLEAN NOT NULL DEFAULT 0,
            status VARCHAR(16) NOT NULL DEFAULT 'unknown',
            last_checked_at DATETIME,
            last_error TEXT,
            last_response_ms INTEGER,
            next_check_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE(host_id, name)
        );
        CREATE INDEX ix_services_host_id ON services (host_id);
        CREATE INDEX ix_services_resource_group_id ON services (resource_group_id);
        CREATE INDEX ix_services_next_check_at ON services (next_check_at);

        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL
        );
        CREATE UNIQUE INDEX ix_users_username ON users (username);

        CREATE TABLE service_probes (
            id INTEGER PRIMARY KEY,
            service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
            key VARCHAR(64) NOT NULL,
            name VARCHAR(100) NOT NULL,
            probe_type VARCHAR(16) NOT NULL,
            process_pattern VARCHAR(500),
            url VARCHAR(1000),
            headers_json TEXT NOT NULL DEFAULT '{}',
            body_json TEXT,
            auth_type VARCHAR(16) NOT NULL DEFAULT 'none',
            auth_username VARCHAR(255),
            auth_secret_encrypted TEXT,
            expected_status INTEGER NOT NULL DEFAULT 200,
            timeout_seconds INTEGER NOT NULL DEFAULT 10,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            last_success BOOLEAN,
            last_checked_at DATETIME,
            last_error TEXT,
            last_response_ms INTEGER,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE(service_id, key)
        );

        CREATE TABLE probe_logs (
            id INTEGER PRIMARY KEY,
            service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
            success BOOLEAN NOT NULL,
            message TEXT NOT NULL,
            response_ms INTEGER,
            checked_at DATETIME NOT NULL
        );

        CREATE TABLE app_migrations (
            version VARCHAR(100) PRIMARY KEY,
            applied_at DATETIME NOT NULL
        );
        """
    )
    now = "2026-08-04 00:00:00"
    connection.execute(
        "INSERT INTO hosts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,
            "legacy-node",
            "10.0.0.10",
            2222,
            "legacy-user",
            "password",
            "encrypted-password",
            None,
            60,
            1,
            "online",
            now,
            None,
            now,
            now,
            now,
        ),
    )
    connection.execute(
        "INSERT INTO resource_groups VALUES (1, 'legacy-group', 'legacy', ?, ?)",
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO services (
            id, host_id, resource_group_id, name, health_rule_json, probe_type,
            process_pattern, headers_json, auth_type, expected_status,
            timeout_seconds, start_command, check_interval, enabled,
            auto_restart, alert_enabled, status, next_check_at, created_at, updated_at
        ) VALUES (
            1, 1, 1, 'legacy-service', '{"probe":"process"}', 'process',
            'legacy-process', '{}', 'none', 200, 10, 'systemctl start legacy',
            60, 1, 1, 0, 'online', ?, ?, ?
        )
        """,
        (now, now, now),
    )
    connection.execute(
        """
        INSERT INTO service_probes (
            id, service_id, key, name, probe_type, process_pattern, headers_json,
            auth_type, expected_status, timeout_seconds, enabled, created_at, updated_at
        ) VALUES (
            1, 1, 'process', '进程', 'process', 'legacy-process', '{}',
            'none', 200, 10, 1, ?, ?
        )
        """,
        (now, now),
    )
    connection.execute(
        "INSERT INTO probe_logs VALUES (1, 1, 1, 'legacy-ok', 12, ?)",
        (now,),
    )
    connection.execute(
        "INSERT INTO users VALUES (1, 'legacy-admin', 'legacy-hash', 1, 1, ?)",
        (now,),
    )
    connection.executemany(
        "INSERT INTO app_migrations VALUES (?, ?)",
        [
            ("20260803_resource_groups_health_rules_v1", now),
            ("20260803_multi_feishu_alerts_v1", now),
        ],
    )
    connection.commit()
    connection.close()


def test_pre_agent_database_migrates_without_data_loss(tmp_path):
    database_path = tmp_path / "legacy.db"
    create_pre_agent_database(database_path)
    database = Database(type("Settings", (), {"database_url": f"sqlite:///{database_path}"})())

    migrate_database(database)
    migrate_database(database)

    inspector = inspect(database.engine)
    host_columns = {column["name"]: column for column in inspector.get_columns("hosts")}
    service_columns = {column["name"]: column for column in inspector.get_columns("services")}
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}
    assert host_columns["execution_mode"]["nullable"] is False
    assert host_columns["port"]["nullable"] is True
    assert service_columns["start_user"]["nullable"] is True
    assert user_columns["token_version"]["nullable"] is False
    assert {"agents", "agent_commands", "agent_report_receipts"} <= set(inspector.get_table_names())

    with database.session_factory() as db:
        host = db.get(Host, 1)
        service = db.get(Service, 1)
        assert host.execution_mode == "ssh"
        assert host.port == 2222
        assert host.username == "legacy-user"
        assert host.password_encrypted == "encrypted-password"
        assert service.start_user is None
        assert db.execute(text("SELECT token_version FROM users WHERE id = 1")).scalar_one() == 0
        assert db.get(ProbeLog, 1).message == "legacy-ok"
        assert db.query(Agent).count() == 0
        assert db.query(AgentCommand).count() == 0
        assert db.query(AgentReportReceipt).count() == 0

    with database.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    indexes = {index["name"] for index in inspector.get_indexes("hosts")}
    assert "ix_hosts_name" in indexes
    assert "ix_hosts_next_check_at" in indexes
