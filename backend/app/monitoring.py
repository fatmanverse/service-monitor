import json
import logging
import re
import shlex
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx
import paramiko
from sqlalchemy.orm import Session

from .health_rules import HealthRuleError, evaluate_rule
from .models import AlertConfig, Host, ProbeLog, Service, ServiceProbe
from .security import SecretCipher
from .start_commands import build_ssh_start_command


logger = logging.getLogger(__name__)
SYSTEMD_UNIT_PATTERN = re.compile(r"^[A-Za-z0-9@_.:-]+$")


@dataclass
class ProbeResult:
    success: bool
    message: str
    response_ms: Optional[int] = None
    restarted: bool = False
    probe_results: Optional[dict] = None

    @property
    def status(self) -> str:
        return "online" if self.success else "offline"


class MonitoringService:
    def __init__(self, cipher: SecretCipher, probe_workers: int = 400):
        self.cipher = cipher
        self.probe_executor = ThreadPoolExecutor(
            max_workers=probe_workers, thread_name_prefix="service-probe"
        )
        self._lock_guard = threading.Lock()
        self._host_locks = {}
        self._service_locks = {}

    def _entity_lock(self, locks, entity_id: int):
        with self._lock_guard:
            return locks.setdefault(entity_id, threading.RLock())

    def shutdown(self) -> None:
        self.probe_executor.shutdown(wait=False)

    def _connect_ssh(self, host: Host) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        options = {
            "hostname": host.hostname,
            "port": host.port,
            "username": host.username,
            "timeout": 10,
            "banner_timeout": 10,
            "auth_timeout": 10,
        }
        if host.auth_type == "password":
            options["password"] = self.cipher.decrypt(host.password_encrypted)
        else:
            options["key_filename"] = host.private_key_path
        client.connect(**options)
        return client

    def check_host(self, db: Session, host: Host) -> ProbeResult:
        with self._entity_lock(self._host_locks, host.id):
            return self._check_host_locked(db, host)

    def _check_host_locked(self, db: Session, host: Host) -> ProbeResult:
        db.refresh(host)
        host.alert_configs
        db.commit()
        previous_status = host.status
        started = time.monotonic()
        try:
            client = self._connect_ssh(host)
            client.close()
            result = ProbeResult(True, "SSH 连接成功", int((time.monotonic() - started) * 1000))
        except Exception as exc:
            result = ProbeResult(False, str(exc), int((time.monotonic() - started) * 1000))
        now = datetime.utcnow()
        host.status = result.status
        host.last_checked_at = now
        host.last_error = None if result.success else result.message
        host.next_check_at = now + timedelta(seconds=host.check_interval)
        db.commit()
        active_alerts = [config for config in host.alert_configs if config.enabled]
        should_alert = (
            (not result.success and previous_status != "offline")
            or (result.success and previous_status == "offline")
        )
        if active_alerts and should_alert:
            alert_result = self._send_host_status_alert(active_alerts, host, previous_status, result)
            if not alert_result.success:
                logger.error("Feishu host alert delivery failed for host %s: %s", host.id, alert_result.message)
        return result

    def check_service(self, db: Session, service: Service, allow_restart: bool = True) -> ProbeResult:
        with self._entity_lock(self._service_locks, service.id):
            return self._check_service_locked(db, service, allow_restart)

    def _check_service_locked(
        self, db: Session, service: Service, allow_restart: bool
    ) -> ProbeResult:
        db.refresh(service)
        service.host
        db.refresh(service.host)
        service.probes
        service.alert_configs
        if service.host.status == "offline":
            service.next_check_at = datetime.utcnow() + timedelta(seconds=service.check_interval)
            db.commit()
            return ProbeResult(False, "节点离线，已暂停服务探活")
        db.commit()
        previous_status = service.status
        result = self._run_service_probes(service)
        if not result.success and allow_restart and service.auto_restart and service.start_command:
            restart_result = self.restart_service(service)
            if restart_result.success:
                result = self._run_service_probes(service)
                result.restarted = True
                if not result.success:
                    result.message = f"启动命令执行成功，但复检失败：{result.message}"
            else:
                result.message = f"探活失败；自动拉起失败：{restart_result.message}"
        now = datetime.utcnow()
        service.status = result.status
        service.last_checked_at = now
        service.last_error = None if result.success else result.message
        service.last_response_ms = result.response_ms
        service.next_check_at = now + timedelta(seconds=service.check_interval)
        db.add(
            ProbeLog(
                service_id=service.id,
                success=result.success,
                message=result.message,
                response_ms=result.response_ms,
            )
        )
        for probe in service.probes:
            probe_result = result.probe_results.get(probe.key) if result.probe_results else None
            if probe_result:
                probe.last_success = probe_result.success
                probe.last_checked_at = now
                probe.last_error = None if probe_result.success else probe_result.message
                probe.last_response_ms = probe_result.response_ms
        db.commit()
        active_alerts = [config for config in service.alert_configs if config.enabled]
        if active_alerts and previous_status in {"online", "offline"} and result.status != previous_status:
            alert_result = self._send_status_alert(active_alerts, service, previous_status, result)
            if not alert_result.success:
                logger.error(
                    "Feishu alert delivery failed for service %s: %s",
                    service.id,
                    alert_result.message,
                )
        return result

    def restart_service(self, service: Service) -> ProbeResult:
        with self._entity_lock(self._service_locks, service.id):
            return self._restart_service_locked(service)

    def restart_and_check(self, db: Session, service: Service) -> ProbeResult:
        with self._entity_lock(self._service_locks, service.id):
            service.host
            db.refresh(service.host)
            if service.host.status == "offline":
                return ProbeResult(False, "节点离线，已暂停服务启动与探活")
            restart_result = self._restart_service_locked(service)
            if not restart_result.success:
                return restart_result
            result = self._check_service_locked(db, service, allow_restart=False)
            result.restarted = True
            return result

    def _restart_service_locked(self, service: Service) -> ProbeResult:
        if not service.start_command:
            return ProbeResult(False, "未配置启动命令")
        started = time.monotonic()
        try:
            client = self._connect_ssh(service.host)
            command = build_ssh_start_command(service.start_command, service.start_user)
            _stdin, stdout, stderr = client.exec_command(command, timeout=30)
            stdout.read()
            error = stderr.read().decode().strip()
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            elapsed = int((time.monotonic() - started) * 1000)
            if exit_code != 0:
                return ProbeResult(False, error or f"启动命令退出码 {exit_code}", elapsed)
            return ProbeResult(True, "启动命令执行成功", elapsed, restarted=True)
        except Exception as exc:
            return ProbeResult(False, str(exc), int((time.monotonic() - started) * 1000))

    def test_alert(self, config: AlertConfig) -> ProbeResult:
        return self._post_feishu(config, "服务监控测试消息：飞书机器人配置有效。")

    def _run_service_probes(self, service: Service) -> ProbeResult:
        enabled_probes = [probe for probe in service.probes if probe.enabled]
        futures = {
            self.probe_executor.submit(self._run_probe, service.host, probe): probe
            for probe in enabled_probes
        }
        results = {}
        for future in as_completed(futures):
            probe = futures[future]
            try:
                results[probe.key] = future.result()
            except Exception as exc:
                results[probe.key] = ProbeResult(False, str(exc))
        try:
            online = evaluate_rule(
                json.loads(service.health_rule_json),
                {key: result.success for key, result in results.items()},
            )
        except (HealthRuleError, json.JSONDecodeError) as exc:
            return ProbeResult(False, f"在线规则求值失败：{exc}", probe_results=results)
        failed = [f"{probe.name}: {results[probe.key].message}" for probe in enabled_probes if not results[probe.key].success]
        response_values = [result.response_ms for result in results.values() if result.response_ms is not None]
        response_ms = max(response_values) if response_values else None
        message = "在线规则满足" if online else "；".join(failed) or "在线规则不满足"
        return ProbeResult(online, message, response_ms, probe_results=results)

    def _run_probe(self, host: Host, probe: ServiceProbe) -> ProbeResult:
        if probe.probe_type == "process":
            return self._probe_process(host, probe)
        return self._probe_http(probe)

    def _probe_process(self, host: Host, probe: ServiceProbe) -> ProbeResult:
        started = time.monotonic()
        try:
            client = self._connect_ssh(host)
            systemd_unit = self._systemd_unit(probe.process_pattern or "")
            command = (
                f"systemctl is-active --quiet -- {shlex.quote(systemd_unit)}"
                if systemd_unit
                else f"pgrep -f -- {shlex.quote(probe.process_pattern or '')} >/dev/null"
            )
            _stdin, stdout, stderr = client.exec_command(command, timeout=probe.timeout_seconds)
            exit_code = stdout.channel.recv_exit_status()
            error = stderr.read().decode().strip()
            client.close()
            elapsed = int((time.monotonic() - started) * 1000)
            if exit_code == 0:
                return ProbeResult(True, f"systemd 服务 {systemd_unit} 在线" if systemd_unit else "进程存在", elapsed)
            return ProbeResult(False, error or (f"systemd 服务 {systemd_unit} 未运行" if systemd_unit else "未找到匹配进程"), elapsed)
        except Exception as exc:
            return ProbeResult(False, str(exc), int((time.monotonic() - started) * 1000))

    @staticmethod
    def _systemd_unit(pattern: str) -> Optional[str]:
        try:
            parts = shlex.split(pattern.strip())
        except ValueError:
            return None
        if len(parts) != 3 or parts[0] != "systemctl" or parts[1] not in {"status", "is-active"}:
            return None
        return parts[2] if SYSTEMD_UNIT_PATTERN.fullmatch(parts[2]) else None

    def _probe_http(self, probe: ServiceProbe) -> ProbeResult:
        headers = json.loads(probe.headers_json or "{}")
        auth = None
        if probe.auth_type == "basic":
            auth = (probe.auth_username or "", self.cipher.decrypt(probe.auth_secret_encrypted) or "")
        elif probe.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.cipher.decrypt(probe.auth_secret_encrypted) or ''}"
        started = time.monotonic()
        try:
            response = httpx.request(
                probe.probe_type.upper(),
                probe.url,
                headers=headers,
                json=json.loads(probe.body_json) if probe.body_json else None,
                auth=auth,
                timeout=probe.timeout_seconds,
            )
            elapsed = int((time.monotonic() - started) * 1000)
            if response.status_code == probe.expected_status:
                return ProbeResult(True, f"HTTP {response.status_code}", elapsed)
            return ProbeResult(
                False,
                f"期望 HTTP {probe.expected_status}，实际 {response.status_code}",
                elapsed,
            )
        except Exception as exc:
            return ProbeResult(False, str(exc), int((time.monotonic() - started) * 1000))

    def _send_status_alert(
        self, configs: list, service: Service, previous_status: str, result: ProbeResult
    ) -> ProbeResult:
        event = "恢复在线" if result.success else "服务离线"
        text = (
            f"{event}\n"
            f"主机：{service.host.name} ({service.host.hostname})\n"
            f"服务：{service.name}\n"
            f"状态：{previous_status} -> {result.status}\n"
            f"详情：{result.message}"
        )
        return self._send_alerts(configs, text)

    def _send_host_status_alert(
        self, configs: list, host: Host, previous_status: str, result: ProbeResult
    ) -> ProbeResult:
        event = "节点恢复在线" if result.success else "节点离线"
        text = (
            f"{event}\n"
            f"节点：{host.name}\n"
            f"地址：{host.hostname}:{host.port}\n"
            f"状态：{previous_status} -> {result.status}\n"
            f"详情：{result.message}"
        )
        return self._send_alerts(configs, text)

    def _send_alerts(self, configs: list, text: str) -> ProbeResult:
        failures = []
        response_times = []
        for config in configs:
            delivery = self._post_feishu(config, text)
            if delivery.response_ms is not None:
                response_times.append(delivery.response_ms)
            if not delivery.success:
                failures.append(f"{config.name}: {delivery.message}")
        response_ms = max(response_times) if response_times else None
        if failures:
            return ProbeResult(False, "；".join(failures), response_ms)
        return ProbeResult(True, f"已发送 {len(configs)} 个飞书机器人", response_ms)

    def _post_feishu(self, config: AlertConfig, text: str) -> ProbeResult:
        if not config.webhook_encrypted:
            return ProbeResult(False, "飞书告警未配置 Webhook")
        started = time.monotonic()
        try:
            response = httpx.post(
                self.cipher.decrypt(config.webhook_encrypted),
                json={"msg_type": "text", "content": {"text": text}},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code", payload.get("StatusCode", 0)) != 0:
                return ProbeResult(False, f"飞书返回失败：{payload}")
            return ProbeResult(True, "飞书消息发送成功", int((time.monotonic() - started) * 1000))
        except Exception as exc:
            return ProbeResult(False, str(exc), int((time.monotonic() - started) * 1000))
