from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import grpc

from .protocol_gen import agent_pb2, agent_pb2_grpc


PROTOCOL_VERSION = 1


class AgentClientError(RuntimeError):
    pass


class AgentAuthenticationError(AgentClientError):
    pass


class AgentApprovalPending(AgentClientError):
    pass


@dataclass(frozen=True)
class AgentClient:
    center_url: str
    ca_file: Optional[str] = None
    tls_server_name: Optional[str] = None
    timeout_seconds: int = 30
    channel: grpc.Channel = field(init=False, repr=False)
    stub: agent_pb2_grpc.AgentControlStub = field(init=False, repr=False)

    def __post_init__(self):
        root_certificates = Path(self.ca_file).read_bytes() if self.ca_file else None
        credentials = grpc.ssl_channel_credentials(root_certificates=root_certificates)
        options = (
            (("grpc.ssl_target_name_override", self.tls_server_name),)
            if self.tls_server_name
            else None
        )
        if options:
            channel = grpc.secure_channel(
                _grpc_target(self.center_url), credentials, options=options
            )
        else:
            channel = grpc.secure_channel(_grpc_target(self.center_url), credentials)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "stub", agent_pb2_grpc.AgentControlStub(channel))

    def enroll(self, identity: dict) -> dict:
        request = agent_pb2.EnrollRequest(**identity)
        response = self._call(self.stub.Enroll, request)
        return {
            "protocol_version": response.protocol_version,
            "agent_uuid": response.agent_uuid,
            "status": response.status,
        }

    def claim(self, agent_uuid: str, claim_token: str) -> dict:
        response = self._call(
            self.stub.Claim,
            agent_pb2.ClaimRequest(
                protocol_version=PROTOCOL_VERSION,
                agent_uuid=agent_uuid,
                claim_token=claim_token,
            ),
        )
        return {
            "protocol_version": response.protocol_version,
            "agent_uuid": response.agent_uuid,
            "agent_secret": response.agent_secret,
        }

    def heartbeat(
        self,
        agent_uuid: str,
        agent_secret: str,
        config_revision: int,
        outbox_size: int,
    ) -> dict:
        response = self._call(
            self.stub.Heartbeat,
            agent_pb2.HeartbeatRequest(
                protocol_version=PROTOCOL_VERSION,
                config_revision=config_revision,
                outbox_size=outbox_size,
            ),
            _agent_metadata(agent_uuid, agent_secret),
        )
        return {
            "protocol_version": response.protocol_version,
            "config_revision": response.config_revision,
            "config_changed": response.config_changed,
            "commands": [
                {
                    "command_id": command.command_id,
                    "service_id": command.service_id,
                    "command_type": command.command_type,
                    "status": "claimed",
                    "expires_at": command.expires_at,
                }
                for command in response.commands
            ],
        }

    def fetch_config(self, agent_uuid: str, agent_secret: str) -> dict:
        response = self._call(
            self.stub.GetConfig,
            agent_pb2.ConfigRequest(protocol_version=PROTOCOL_VERSION),
            _agent_metadata(agent_uuid, agent_secret),
        )
        return {
            "protocol_version": response.protocol_version,
            "config_revision": response.config_revision,
            "host_id": response.host_id,
            "services": [_service_config(service) for service in response.services],
        }

    def upload_reports(
        self, agent_uuid: str, agent_secret: str, reports: list
    ) -> dict:
        response = self._call(
            self.stub.Report,
            agent_pb2.ReportRequest(
                protocol_version=PROTOCOL_VERSION,
                reports=[_report(report) for report in reports],
            ),
            _agent_metadata(agent_uuid, agent_secret),
        )
        return {
            "protocol_version": response.protocol_version,
            "accepted": response.accepted,
            "duplicates": response.duplicates,
        }

    def _call(self, rpc, request, metadata=()):
        try:
            response = rpc(
                request,
                timeout=self.timeout_seconds,
                metadata=metadata,
            )
        except grpc.RpcError as exc:
            detail = exc.details() or str(exc)
            if exc.code() == grpc.StatusCode.UNAUTHENTICATED:
                raise AgentAuthenticationError(detail) from exc
            if exc.code() == grpc.StatusCode.FAILED_PRECONDITION:
                raise AgentApprovalPending(detail) from exc
            raise AgentClientError(f"监控中心 RPC 失败：{detail}") from exc
        if response.protocol_version != PROTOCOL_VERSION:
            raise AgentClientError("监控中心协议版本不受支持")
        return response


def _grpc_target(center_url: str) -> str:
    if "://" not in center_url:
        return center_url.rstrip("/")
    parsed = urlparse(center_url)
    if parsed.scheme not in {"grpc", "grpcs", "https"} or not parsed.netloc:
        raise ValueError("center_url 必须是 TLS gRPC 地址")
    return parsed.netloc


def _agent_metadata(agent_uuid: str, agent_secret: str):
    if not agent_uuid or not agent_secret:
        raise AgentAuthenticationError("Agent 认证信息缺失")
    return (
        ("x-agent-id", agent_uuid),
        ("authorization", f"Bearer {agent_secret}"),
    )


def _service_config(service) -> dict:
    return {
        "id": service.id,
        "name": service.name,
        "probes": [
            {
                "key": probe.key,
                "name": probe.name,
                "probe_type": probe.probe_type,
                "process_pattern": probe.process_pattern if probe.HasField("process_pattern") else None,
                "url": probe.url if probe.HasField("url") else None,
                "headers": __import__("json").loads(probe.headers_json),
                "body": __import__("json").loads(probe.body_json) if probe.HasField("body_json") else None,
                "auth_type": probe.auth_type,
                "auth_username": probe.auth_username if probe.HasField("auth_username") else None,
                "auth_secret": probe.auth_secret if probe.HasField("auth_secret") else None,
                "expected_status": probe.expected_status,
                "timeout_seconds": probe.timeout_seconds,
            }
            for probe in service.probes
        ],
        "health_rule": __import__("json").loads(service.health_rule_json),
        "start_command": service.start_command if service.HasField("start_command") else None,
        "start_user": service.start_user if service.HasField("start_user") else None,
        "check_interval": service.check_interval,
        "auto_restart": service.auto_restart,
    }


def _report(report: dict):
    message = agent_pb2.ServiceReport(
        report_id=report["report_id"],
        report_sequence=report["report_sequence"],
        service_id=report["service_id"],
        success=report["success"],
        message=report["message"],
        restarted=report.get("restarted", False),
        occurred_at=report["occurred_at"],
        probes=[agent_pb2.ProbeReport(**probe) for probe in report.get("probes", [])],
    )
    if report.get("response_ms") is not None:
        message.response_ms = report["response_ms"]
    if report.get("command_id") is not None:
        message.command_id = report["command_id"]
    return message
