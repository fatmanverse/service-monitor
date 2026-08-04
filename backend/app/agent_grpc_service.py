from datetime import datetime
import json

import grpc
from fastapi import HTTPException
from sqlalchemy import select

from .agent_protocol import build_agent_config, claim_pending_commands
from .agent_reports import process_agent_reports
from .agent_schemas import (
    AgentClaimInput,
    AgentEnrollInput,
    AgentHeartbeatInput,
    AgentReportsInput,
)
from .agent_security import EnrollmentRateLimiter, verify_agent_secret
from .agent_service import claim_agent_secret, enroll_agent
from .grpc_errors import abort_rpc
from .models import Agent
from .monitoring import ProbeResult
from .protocol_gen import agent_pb2, agent_pb2_grpc


class AgentControlService(agent_pb2_grpc.AgentControlServicer):
    def __init__(self, database, settings, cipher, monitor):
        self.database = database
        self.settings = settings
        self.cipher = cipher
        self.monitor = monitor
        self.enrollment_limiter = EnrollmentRateLimiter()

    def Enroll(self, request, context):
        try:
            _ensure_request_size(request, 8192)
            payload = AgentEnrollInput(**_message_dict(request))
            peer_ip = _peer_ip(context)
            if not self.enrollment_limiter.allow(f"ip:{peer_ip}") or not self.enrollment_limiter.allow(
                f"agent:{payload.agent_uuid}"
            ):
                raise HTTPException(status_code=429, detail="注册申请过于频繁")
            with self.database.session_factory() as db:
                agent = enroll_agent(db, payload, self.settings)
                return agent_pb2.EnrollResponse(
                    protocol_version=1,
                    agent_uuid=agent.agent_uuid,
                    status=agent.status,
                )
        except Exception as exc:
            abort_rpc(context, exc)
            return agent_pb2.EnrollResponse()

    def Claim(self, request, context):
        try:
            payload = AgentClaimInput(**_message_dict(request))
            with self.database.session_factory() as db:
                secret = claim_agent_secret(
                    db,
                    payload.agent_uuid,
                    payload.claim_token,
                    self.settings,
                    self.cipher,
                )
            return agent_pb2.ClaimResponse(
                protocol_version=1,
                agent_uuid=payload.agent_uuid,
                agent_secret=secret,
            )
        except Exception as exc:
            abort_rpc(context, exc)
            return agent_pb2.ClaimResponse()

    def Heartbeat(self, request, context):
        try:
            _ensure_protocol_version(request.protocol_version)
            agent = self._authenticated_agent(context)
            payload = AgentHeartbeatInput(**_message_dict(request))
            with self.database.session_factory() as db:
                agent = db.get(Agent, agent.id)
                previous_status = agent.host.status if agent.host else "unknown"
                agent.last_seen_at = datetime.utcnow()
                agent.last_ip = _peer_ip(context)
                if agent.pending_secret_encrypted:
                    agent.pending_secret_encrypted = None
                    agent.claim_token_hash = None
                if agent.host:
                    agent.host.status = "online"
                    agent.host.last_checked_at = agent.last_seen_at
                    agent.host.last_error = None
                db.commit()
                if agent.host and previous_status == "offline":
                    active_alerts = [
                        config for config in agent.host.alert_configs if config.enabled
                    ]
                    if active_alerts:
                        self.monitor._send_host_status_alert(
                            active_alerts,
                            agent.host,
                            previous_status,
                            ProbeResult(True, "Agent 心跳恢复"),
                        )
                commands = claim_pending_commands(db, agent)
                return agent_pb2.HeartbeatResponse(
                    protocol_version=1,
                    config_revision=agent.config_revision,
                    config_changed=payload.config_revision < agent.config_revision,
                    commands=[
                        agent_pb2.AgentCommand(
                            command_id=command.command_id,
                            service_id=command.service_id,
                            command_type=command.command_type,
                            expires_at=command.expires_at.isoformat(),
                        )
                        for command in commands
                    ],
                )
        except Exception as exc:
            abort_rpc(context, exc)
            return agent_pb2.HeartbeatResponse()

    def GetConfig(self, request, context):
        try:
            _ensure_protocol_version(request.protocol_version)
            agent = self._authenticated_agent(context)
            with self.database.session_factory() as db:
                payload = build_agent_config(db, db.get(Agent, agent.id), self.cipher)
            return _config_response(payload)
        except Exception as exc:
            abort_rpc(context, exc)
            return agent_pb2.ConfigResponse()

    def Report(self, request, context):
        try:
            _ensure_protocol_version(request.protocol_version)
            agent = self._authenticated_agent(context)
            payload = AgentReportsInput(
                protocol_version=request.protocol_version,
                reports=[_report_dict(report) for report in request.reports],
            )
            with self.database.session_factory() as db:
                result = process_agent_reports(db, db.get(Agent, agent.id), payload, self.monitor)
            return agent_pb2.ReportResponse(
                protocol_version=1,
                accepted=result.accepted,
                duplicates=result.duplicates,
            )
        except Exception as exc:
            abort_rpc(context, exc)
            return agent_pb2.ReportResponse()

    def _authenticated_agent(self, context):
        metadata = dict(context.invocation_metadata())
        agent_uuid = metadata.get("x-agent-id", "")
        authorization = metadata.get("authorization", "")
        secret = authorization.removeprefix("Bearer ")
        with self.database.session_factory() as db:
            agent = db.scalar(select(Agent).where(Agent.agent_uuid == agent_uuid))
            if (
                not agent
                or agent.status != "approved"
                or not agent.secret_hash
                or not verify_agent_secret(secret, agent.secret_hash, self.settings.app_secret)
            ):
                raise HTTPException(status_code=401, detail="Agent 认证失败")
            return agent


def _message_dict(message):
    return {field.name: getattr(message, field.name) for field in message.DESCRIPTOR.fields}


def _ensure_protocol_version(version):
    if version != 1:
        raise HTTPException(status_code=409, detail="不支持的协议主版本")


def _ensure_request_size(request, limit):
    if request.ByteSize() > limit:
        raise HTTPException(status_code=413, detail="注册申请过大")


def _peer_ip(context):
    return context.peer().rsplit(":", 1)[-1] if context.peer() else ""


def _config_response(payload):
    return agent_pb2.ConfigResponse(
        protocol_version=payload.protocol_version,
        config_revision=payload.config_revision,
        host_id=payload.host_id,
        services=[
            _service_config(service)
            for service in payload.services
        ],
    )


def _service_config(service):
    message = agent_pb2.ServiceConfig(
        id=service.id,
        name=service.name,
        probes=[_probe_config(probe) for probe in service.probes],
        health_rule_json=json.dumps(service.health_rule, ensure_ascii=False),
        check_interval=service.check_interval,
        auto_restart=service.auto_restart,
    )
    if service.start_command is not None:
        message.start_command = service.start_command
    if service.start_user is not None:
        message.start_user = service.start_user
    return message


def _probe_config(probe):
    message = agent_pb2.ProbeConfig(
        key=probe.key,
        name=probe.name,
        probe_type=probe.probe_type,
        headers_json=json.dumps(probe.headers, ensure_ascii=False),
        auth_type=probe.auth_type,
        expected_status=probe.expected_status,
        timeout_seconds=probe.timeout_seconds,
    )
    if probe.process_pattern is not None:
        message.process_pattern = probe.process_pattern
    if probe.url is not None:
        message.url = probe.url
    if probe.body is not None:
        message.body_json = json.dumps(probe.body, ensure_ascii=False)
    if probe.auth_username is not None:
        message.auth_username = probe.auth_username
    if probe.auth_secret is not None:
        message.auth_secret = probe.auth_secret
    return message


def _report_dict(report):
    result = {
        "report_id": report.report_id,
        "report_sequence": report.report_sequence,
        "service_id": report.service_id,
        "success": report.success,
        "message": report.message,
        "response_ms": report.response_ms if report.HasField("response_ms") else None,
        "restarted": report.restarted,
        "occurred_at": report.occurred_at,
        "probes": [],
        "command_id": report.command_id if report.HasField("command_id") else None,
    }
    result["probes"] = [
        {
            "key": probe.key,
            "success": probe.success,
            "message": probe.message,
            "response_ms": probe.response_ms if probe.HasField("response_ms") else None,
        }
        for probe in report.probes
    ]
    return result
