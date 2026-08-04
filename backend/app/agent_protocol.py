import json
from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .agent_schemas import (
    AgentCommandContract,
    AgentConfigOutput,
    AgentProbeConfig,
    AgentServiceConfig,
)
from .models import Agent, AgentCommand, Service
from .security import SecretCipher


def bump_agent_config_revision(db: Session, host_id: int) -> None:
    agent = db.scalar(
        select(Agent).where(Agent.host_id == host_id, Agent.status == "approved")
    )
    if agent:
        agent.config_revision += 1


def build_agent_config(
    db: Session, agent: Agent, cipher: SecretCipher
) -> AgentConfigOutput:
    if not agent.host_id:
        raise HTTPException(status_code=409, detail="Agent 尚未绑定主机")
    services = db.scalars(
        select(Service)
        .options(selectinload(Service.probes))
        .where(
            Service.host_id == agent.host_id,
            Service.enabled.is_(True),
        )
        .order_by(Service.id)
    ).all()
    return AgentConfigOutput(
        config_revision=agent.config_revision,
        host_id=agent.host_id,
        services=[
            AgentServiceConfig(
                id=service.id,
                name=service.name,
                probes=[
                    AgentProbeConfig(
                        key=probe.key,
                        name=probe.name,
                        probe_type=probe.probe_type,
                        process_pattern=probe.process_pattern,
                        url=probe.url,
                        headers=json.loads(probe.headers_json or "{}"),
                        body=json.loads(probe.body_json) if probe.body_json else None,
                        auth_type=probe.auth_type,
                        auth_username=probe.auth_username,
                        auth_secret=cipher.decrypt(probe.auth_secret_encrypted),
                        expected_status=probe.expected_status,
                        timeout_seconds=probe.timeout_seconds,
                    )
                    for probe in service.probes
                    if probe.enabled
                ],
                health_rule=json.loads(service.health_rule_json),
                start_command=service.start_command,
                start_user=service.start_user,
                check_interval=service.check_interval,
                auto_restart=service.auto_restart,
            )
            for service in services
        ],
    )


def queue_agent_command(
    db: Session,
    service: Service,
    command_type: str,
    offline_seconds: int,
) -> AgentCommand:
    agent = service.host.agent
    cutoff = datetime.utcnow() - timedelta(seconds=offline_seconds)
    if (
        service.host.execution_mode != "agent"
        or not agent
        or agent.status != "approved"
        or not agent.last_seen_at
        or agent.last_seen_at < cutoff
    ):
        raise HTTPException(status_code=409, detail="Agent 当前离线，无法创建命令")
    command = AgentCommand(
        command_id=str(uuid4()),
        agent_id=agent.id,
        service_id=service.id,
        command_type=command_type,
        status="pending",
        payload_json="{}",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


def claim_pending_commands(db: Session, agent: Agent) -> List[AgentCommandContract]:
    now = datetime.utcnow()
    expired = db.scalars(
        select(AgentCommand).where(
            AgentCommand.agent_id == agent.id,
            AgentCommand.status.in_({"pending", "claimed"}),
            AgentCommand.expires_at <= now,
        )
    ).all()
    for command in expired:
        command.status = "expired"
        command.finished_at = now
    commands = db.scalars(
        select(AgentCommand)
        .where(
            AgentCommand.agent_id == agent.id,
            AgentCommand.status.in_({"pending", "claimed"}),
            AgentCommand.expires_at > now,
        )
        .order_by(AgentCommand.created_at)
        .limit(100)
    ).all()
    for command in commands:
        if command.status == "pending":
            command.status = "claimed"
            command.claimed_at = now
    db.commit()
    return [
        AgentCommandContract(
            command_id=command.command_id,
            service_id=command.service_id,
            command_type=command.command_type,
            status="claimed",
            expires_at=command.expires_at,
        )
        for command in commands
    ]
