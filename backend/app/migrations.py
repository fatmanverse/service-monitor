import json
from datetime import datetime

from sqlalchemy import inspect, select, text

from .database import Database
from .models import (
    AlertConfig,
    AppMigration,
    ResourceGroup,
    Service,
    ServiceAlertConfig,
    ServiceProbe,
    UserResourceGroup,
    UserService,
)


MIGRATION_VERSION = "20260803_resource_groups_health_rules_v1"
ALERT_MIGRATION_VERSION = "20260803_multi_feishu_alerts_v1"
AGENT_MIGRATION_VERSION = "20260804_agent_persistence_v1"


def migrate_database(database: Database) -> None:
    database.create_all()
    inspector = inspect(database.engine)
    host_columns = {column["name"]: column for column in inspector.get_columns("hosts")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    service_columns = {column["name"] for column in inspector.get_columns("services")}
    alert_columns = {column["name"] for column in inspector.get_columns("alert_configs")}
    with database.engine.begin() as connection:
        if "resource_group_id" not in service_columns:
            connection.execute(
                text(
                    "ALTER TABLE services ADD COLUMN resource_group_id INTEGER "
                    "REFERENCES resource_groups(id) ON DELETE RESTRICT"
                )
            )
        if "health_rule_json" not in service_columns:
            connection.execute(text("ALTER TABLE services ADD COLUMN health_rule_json TEXT"))
        if "name" not in alert_columns:
            connection.execute(text("ALTER TABLE alert_configs ADD COLUMN name VARCHAR(100)"))
        if "created_at" not in alert_columns:
            connection.execute(text("ALTER TABLE alert_configs ADD COLUMN created_at DATETIME"))
        if "execution_mode" not in host_columns:
            connection.execute(
                text(
                    "ALTER TABLE hosts ADD COLUMN execution_mode VARCHAR(16) "
                    "NOT NULL DEFAULT 'ssh'"
                )
            )
        if "start_user" not in service_columns:
            connection.execute(text("ALTER TABLE services ADD COLUMN start_user VARCHAR(100)"))
        if "token_version" not in user_columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
            )
    if not host_columns["port"]["nullable"]:
        _rebuild_hosts_with_nullable_port(database)
    with database.session_factory() as db:
        if not db.get(AppMigration, MIGRATION_VERSION):
            _migrate_resource_groups(db)
            db.add(AppMigration(version=MIGRATION_VERSION))
            db.commit()
        if not db.get(AppMigration, ALERT_MIGRATION_VERSION):
            _migrate_alert_configs(db)
            db.flush()
            db.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_alert_configs_name ON alert_configs (name)")
            )
            db.add(AppMigration(version=ALERT_MIGRATION_VERSION))
            db.commit()
        if not db.get(AppMigration, AGENT_MIGRATION_VERSION):
            db.add(AppMigration(version=AGENT_MIGRATION_VERSION))
            db.commit()


def _rebuild_hosts_with_nullable_port(database: Database) -> None:
    connection = database.engine.raw_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("DROP TABLE IF EXISTS hosts__agent_migration")
        cursor.execute(
            """
            CREATE TABLE hosts__agent_migration (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                hostname VARCHAR(255) NOT NULL,
                port INTEGER,
                username VARCHAR(100) NOT NULL,
                auth_type VARCHAR(16) NOT NULL DEFAULT 'password',
                execution_mode VARCHAR(16) NOT NULL DEFAULT 'ssh',
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
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO hosts__agent_migration (
                id, name, hostname, port, username, auth_type, execution_mode,
                password_encrypted, private_key_path, check_interval, enabled,
                status, last_checked_at, last_error, next_check_at, created_at, updated_at
            )
            SELECT
                id, name, hostname, port, username, auth_type, execution_mode,
                password_encrypted, private_key_path, check_interval, enabled,
                status, last_checked_at, last_error, next_check_at, created_at, updated_at
            FROM hosts
            """
        )
        cursor.execute("DROP TABLE hosts")
        cursor.execute("ALTER TABLE hosts__agent_migration RENAME TO hosts")
        cursor.execute("CREATE UNIQUE INDEX ix_hosts_name ON hosts (name)")
        cursor.execute("CREATE INDEX ix_hosts_execution_mode ON hosts (execution_mode)")
        cursor.execute("CREATE INDEX ix_hosts_next_check_at ON hosts (next_check_at)")
        violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Agent migration foreign key check failed: {violations}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        connection.close()


def _migrate_resource_groups(db) -> None:
    services = db.scalars(select(Service).order_by(Service.id)).all()
    for service in services:
        if service.resource_group_id and service.health_rule_json and service.probes:
            continue
        group = ResourceGroup(
            name=_unique_group_name(db, f"迁移-{service.id}-{service.name}"),
            description="由旧服务授权自动迁移，可在资源组管理中合并。",
        )
        db.add(group)
        db.flush()
        service.resource_group_id = group.id
        probe_key = f"legacy-{service.id}"
        probe = ServiceProbe(
            service_id=service.id,
            key=probe_key,
            name="迁移探活项",
            probe_type=service.probe_type,
            process_pattern=service.process_pattern,
            url=service.url,
            headers_json=service.headers_json,
            body_json=service.body_json,
            auth_type=service.auth_type,
            auth_username=service.auth_username,
            auth_secret_encrypted=service.auth_secret_encrypted,
            expected_status=service.expected_status,
            timeout_seconds=service.timeout_seconds,
            enabled=True,
        )
        db.add(probe)
        service.health_rule_json = json.dumps({"probe": probe_key})
        legacy_user_ids = db.scalars(
            select(UserService.user_id).where(UserService.service_id == service.id)
        ).all()
        for user_id in legacy_user_ids:
            if not db.get(UserResourceGroup, (user_id, group.id)):
                db.add(UserResourceGroup(user_id=user_id, resource_group_id=group.id))


def _migrate_alert_configs(db) -> None:
    legacy_config = db.get(AlertConfig, 1)
    if legacy_config:
        legacy_config.name = legacy_config.name or _unique_alert_name(db, "默认飞书机器人", legacy_config.id)
        legacy_services = db.scalars(
            select(Service.id).where(Service.alert_enabled.is_(True))
        ).all()
        for service_id in legacy_services:
            if not db.get(ServiceAlertConfig, (service_id, legacy_config.id)):
                db.add(ServiceAlertConfig(service_id=service_id, alert_config_id=legacy_config.id))
    for config in db.scalars(select(AlertConfig).order_by(AlertConfig.id)).all():
        if not config.name:
            config.name = _unique_alert_name(db, f"飞书机器人-{config.id}", config.id)
        if not config.created_at:
            config.created_at = config.updated_at or datetime.utcnow()


def _unique_group_name(db, base_name: str) -> str:
    candidate = base_name[:100]
    suffix = 1
    while db.scalar(select(ResourceGroup.id).where(ResourceGroup.name == candidate)):
        suffix += 1
        marker = f"-{suffix}"
        candidate = f"{base_name[:100 - len(marker)]}{marker}"
    return candidate


def _unique_alert_name(db, base_name: str, current_id: int = None) -> str:
    candidate = base_name[:100]
    suffix = 1
    query = select(AlertConfig.id).where(AlertConfig.name == candidate)
    if current_id is not None:
        query = query.where(AlertConfig.id != current_id)
    while db.scalar(query):
        suffix += 1
        marker = f"-{suffix}"
        candidate = f"{base_name[:100 - len(marker)]}{marker}"
        query = select(AlertConfig.id).where(AlertConfig.name == candidate)
        if current_id is not None:
            query = query.where(AlertConfig.id != current_id)
    return candidate
