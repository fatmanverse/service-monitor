import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

from .commands import execute_start_command
from .health_rules import HealthRuleError, evaluate_rule, validate_rule
from .probes import ProbeResult, run_probe


logger = logging.getLogger(__name__)


class AgentEngine:
    def __init__(
        self,
        storage,
        probe_runner: Callable = run_probe,
        start_runner: Callable = execute_start_command,
        probe_workers: int = 32,
    ):
        self.storage = storage
        self.probe_runner = probe_runner
        self.start_runner = start_runner
        self.probe_workers = probe_workers

    def check_service(
        self,
        service: dict,
        command_id: Optional[str] = None,
        allow_restart: bool = True,
    ) -> dict:
        probes = service.get("probes") or []
        validate_rule(service["health_rule"], {probe["key"] for probe in probes})
        results = self._run_probes(probes)
        online = evaluate_rule(
            service["health_rule"],
            {key: result.success for key, result in results.items()},
        )
        restarted = False
        restart_message = None
        if (
            not online
            and allow_restart
            and service.get("auto_restart")
            and service.get("start_command")
        ):
            restart_result = self.start_runner(service)
            restart_message = restart_result.message
            if restart_result.success:
                restarted = True
                results = self._run_probes(probes)
                online = evaluate_rule(
                    service["health_rule"],
                    {key: result.success for key, result in results.items()},
                )
        report = self._build_report(
            service, results, online, restarted, restart_message, command_id
        )
        return self.storage.enqueue_report(report)

    def execute_command(self, command: dict, services: dict) -> dict:
        command_id = command["command_id"]
        existing = self.storage.command_result(command_id)
        if existing is not None:
            return existing
        service = services.get(command["service_id"])
        if not service:
            raise ValueError("命令引用了不存在的服务")
        if command["command_type"] == "probe_service":
            report = self.check_service(service, command_id=command_id, allow_restart=False)
        elif command["command_type"] == "restart_service":
            restart_result = self.start_runner(service)
            if restart_result.success:
                report = self.check_service(service, command_id=command_id, allow_restart=False)
                report["restarted"] = True
                if not report["success"]:
                    report["message"] = f"启动命令执行成功，但复检失败：{report['message']}"
            else:
                report = self._failed_command_report(service, command_id, restart_result.message)
                report = self.storage.enqueue_report(report)
        else:
            raise ValueError("不支持的命令类型")
        self.storage.save_command_result(command_id, report)
        return report

    def _run_probes(self, probes: list) -> dict:
        results = {}
        with ThreadPoolExecutor(max_workers=min(self.probe_workers, max(len(probes), 1))) as pool:
            futures = {pool.submit(self.probe_runner, probe): probe for probe in probes}
            for future in as_completed(futures):
                probe = futures[future]
                try:
                    results[probe["key"]] = future.result()
                except Exception as exc:
                    results[probe["key"]] = ProbeResult(
                        probe["key"], False, str(exc)
                    )
        return results

    @staticmethod
    def _build_report(
        service: dict,
        results: dict,
        online: bool,
        restarted: bool,
        restart_message: Optional[str],
        command_id: Optional[str],
    ) -> dict:
        failed = [result.message for result in results.values() if not result.success]
        if online:
            message = "在线规则满足"
        elif restart_message:
            message = f"探活失败；自动拉起结果：{restart_message}；{'；'.join(failed)}"
        else:
            message = "；".join(failed) or "在线规则不满足"
        response_values = [
            result.response_ms for result in results.values() if result.response_ms is not None
        ]
        return {
            "service_id": service["id"],
            "success": online,
            "message": message,
            "response_ms": max(response_values) if response_values else None,
            "restarted": restarted,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "probes": [
                {
                    "key": result.key,
                    "success": result.success,
                    "message": result.message,
                    "response_ms": result.response_ms,
                }
                for result in results.values()
            ],
            "command_id": command_id,
        }

    @staticmethod
    def _failed_command_report(service: dict, command_id: str, message: str) -> dict:
        return {
            "service_id": service["id"],
            "success": False,
            "message": f"启动失败：{message}",
            "response_ms": None,
            "restarted": False,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "probes": [],
            "command_id": command_id,
        }
