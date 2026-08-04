import getpass
import logging
import platform
import time
from pathlib import Path

from . import __version__
from .client import AgentApprovalPending, AgentAuthenticationError, PROTOCOL_VERSION
from .engine import AgentEngine


logger = logging.getLogger(__name__)


def host_identity(agent_uuid: str, claim_token: str) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "agent_uuid": agent_uuid,
        "claim_token": claim_token,
        "hostname": platform.node() or "unknown",
        "runtime_user": getpass.getuser(),
        "os_release": _os_release(),
        "architecture": _architecture(),
        "glibc_version": platform.libc_ver()[1] or "unknown",
        "agent_version": __version__,
    }


def _os_release() -> str:
    path = Path("/etc/os-release")
    if path.exists():
        values = {}
        for line in path.read_text(errors="replace").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
        return values.get("PRETTY_NAME") or values.get("NAME") or platform.system()
    return platform.platform()


def _architecture() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "x86_64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    return machine


class AgentRuntime:
    def __init__(self, config, storage, client, engine=None, clock=time.monotonic):
        self.config = config
        self.storage = storage
        self.client = client
        self.engine = engine or AgentEngine(storage)
        self.clock = clock
        self.next_heartbeat_at = 0.0
        self.next_service_checks = {}

    def sync_once(self) -> bool:
        agent_uuid, claim_token = self.storage.ensure_identity()
        agent_secret = self.storage.get("agent_secret")
        if not agent_secret:
            self.client.enroll(host_identity(agent_uuid, claim_token))
            try:
                claimed = self.client.claim(agent_uuid, claim_token)
            except AgentApprovalPending:
                return False
            agent_secret = claimed["agent_secret"]
            self.storage.save_secret(agent_secret)

        pending = self.storage.pending_reports()
        heartbeat = self.client.heartbeat(
            agent_uuid,
            agent_secret,
            self.storage.config_revision(),
            len(pending),
        )
        if heartbeat["config_changed"]:
            config_payload = self.client.fetch_config(agent_uuid, agent_secret)
            self.storage.save_config(config_payload, agent_secret)
        cached_config = self.storage.load_config(agent_secret)
        if cached_config:
            services = {service["id"]: service for service in cached_config["services"]}
            self._drop_removed_services(services)
            for command in heartbeat["commands"]:
                self.engine.execute_command(command, services)
        pending = self.storage.pending_reports()
        if pending:
            self.client.upload_reports(agent_uuid, agent_secret, pending)
            self.storage.acknowledge_reports(
                [report["report_id"] for report in pending]
            )
        return True

    def run_due_services(self) -> int:
        agent_secret = self.storage.get("agent_secret")
        if not agent_secret:
            return 0
        cached_config = self.storage.load_config(agent_secret)
        if not cached_config:
            return 0
        now = self.clock()
        checked = 0
        for service in cached_config["services"]:
            service_id = service["id"]
            if now < self.next_service_checks.get(service_id, 0.0):
                continue
            try:
                self.engine.check_service(service)
            except Exception:
                logger.exception("服务 %s 本地探活执行失败", service_id)
            finally:
                self.next_service_checks[service_id] = (
                    self.clock() + service["check_interval"]
                )
            checked += 1
        return checked

    def run_forever(self) -> None:
        retry_seconds = 1
        while True:
            now = self.clock()
            if now >= self.next_heartbeat_at:
                try:
                    self.sync_once()
                except AgentAuthenticationError:
                    raise
                except Exception:
                    logger.exception("Agent 与监控中心同步失败")
                    self.next_heartbeat_at = self.clock() + retry_seconds
                    retry_seconds = min(retry_seconds * 2, self.config.heartbeat_interval)
                else:
                    retry_seconds = 1
                    self.next_heartbeat_at = (
                        self.clock() + self.config.heartbeat_interval
                    )
            self.run_due_services()
            time.sleep(1)

    def _drop_removed_services(self, services: dict) -> None:
        active_ids = set(services)
        self.next_service_checks = {
            service_id: due
            for service_id, due in self.next_service_checks.items()
            if service_id in active_ids
        }
