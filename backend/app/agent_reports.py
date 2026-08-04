import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from .agent_schemas import AgentReportsInput, AgentReportsOutput
from .models import (
    Agent,
    AgentCommand,
    AgentReportReceipt,
    ProbeLog,
    Service,
)
from .monitoring import MonitoringService, ProbeResult


logger = logging.getLogger(__name__)


@dataclass
class ServiceTransition:
    service: Service
    previous_status: str
    result: ProbeResult


def _load_services(db: Session, service_ids: set) -> dict:
    services = db.scalars(
        select(Service)
        .options(
            joinedload(Service.host),
            selectinload(Service.probes),
            selectinload(Service.alert_configs),
        )
        .where(Service.id.in_(service_ids))
    ).unique().all()
    return {service.id: service for service in services}


def process_agent_reports(
    db: Session,
    agent: Agent,
    payload: AgentReportsInput,
    monitor: MonitoringService,
) -> AgentReportsOutput:
    reports = sorted(payload.reports, key=lambda report: report.report_sequence)
    services = _load_services(db, {report.service_id for report in reports})
    for report in reports:
        service = services.get(report.service_id)
        if not service or service.host_id != agent.host_id:
            raise HTTPException(status_code=403, detail="报告包含未绑定服务")

    accepted = 0
    duplicates = 0
    initial_status = {}
    final_results = {}
    for report in reports:
        receipt = db.get(AgentReportReceipt, (agent.id, report.report_id))
        sequence_receipt = db.scalar(
            select(AgentReportReceipt).where(
                AgentReportReceipt.agent_id == agent.id,
                AgentReportReceipt.report_sequence == report.report_sequence,
            )
        )
        if receipt or sequence_receipt:
            duplicates += 1
            continue
        service = services[report.service_id]
        db.add(
            AgentReportReceipt(
                agent_id=agent.id,
                report_id=report.report_id,
                report_sequence=report.report_sequence,
            )
        )
        occurred_at = report.occurred_at.replace(tzinfo=None)
        db.add(
            ProbeLog(
                service_id=service.id,
                success=report.success,
                message=report.message,
                response_ms=report.response_ms,
                checked_at=occurred_at,
            )
        )
        accepted += 1
        if report.report_sequence <= agent.last_report_sequence:
            continue
        initial_status.setdefault(service.id, service.status)
        service.status = "online" if report.success else "offline"
        service.last_checked_at = occurred_at
        service.last_error = None if report.success else report.message
        service.last_response_ms = report.response_ms
        probe_by_key = {probe.key: probe for probe in service.probes}
        for probe_report in report.probes:
            probe = probe_by_key.get(probe_report.key)
            if not probe:
                raise HTTPException(status_code=422, detail="报告包含未知探活项")
            probe.last_success = probe_report.success
            probe.last_checked_at = occurred_at
            probe.last_error = None if probe_report.success else probe_report.message
            probe.last_response_ms = probe_report.response_ms
        if report.command_id:
            command = db.get(AgentCommand, report.command_id)
            if (
                not command
                or command.agent_id != agent.id
                or command.service_id != service.id
            ):
                raise HTTPException(status_code=403, detail="命令结果不属于当前 Agent")
            command.status = "succeeded" if report.success else "failed"
            command.result_json = report.model_dump_json()
            command.finished_at = datetime.utcnow()
        agent.last_report_sequence = report.report_sequence
        final_results[service.id] = ProbeResult(
            report.success,
            report.message,
            report.response_ms,
            restarted=report.restarted,
        )
    db.commit()

    for service_id, result in final_results.items():
        service = services[service_id]
        previous_status = initial_status[service_id]
        active_alerts = [config for config in service.alert_configs if config.enabled]
        if (
            service.host.status == "online"
            and active_alerts
            and previous_status in {"online", "offline"}
            and result.status != previous_status
        ):
            delayed = ProbeResult(
                result.success,
                f"延迟上报：{result.message}",
                result.response_ms,
                restarted=result.restarted,
            )
            delivery = monitor._send_status_alert(
                active_alerts, service, previous_status, delayed
            )
            if not delivery.success:
                logger.error(
                    "Feishu delayed Agent alert failed for service %s: %s",
                    service.id,
                    delivery.message,
                )
    return AgentReportsOutput(accepted=accepted, duplicates=duplicates)
