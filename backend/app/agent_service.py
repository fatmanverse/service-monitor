from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .agent_schemas import AgentApproveInput, AgentEnrollInput, AgentOutput
from .agent_security import generate_agent_secret, hash_agent_secret, verify_agent_secret
from .config import Settings
from .models import Agent, Host
from .schemas import HostOutput
from .security import SecretCipher
from .serializers import host_output


def agent_load_query():
    return select(Agent).options(
        selectinload(Agent.host).selectinload(Host.alert_configs)
    )


def list_agents(db: Session) -> List[Agent]:
    return db.scalars(agent_load_query().order_by(Agent.created_at.desc())).all()


def get_agent(db: Session, agent_id: int) -> Agent:
    agent = db.scalar(agent_load_query().where(Agent.id == agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


def serialize_agent(agent: Agent, ssh_credentials_removed: bool = False) -> AgentOutput:
    host: Optional[HostOutput] = host_output(agent.host) if agent.host else None
    return AgentOutput(
        id=agent.id,
        agent_uuid=agent.agent_uuid,
        status=agent.status,
        hostname=agent.hostname,
        runtime_user=agent.runtime_user,
        os_release=agent.os_release,
        architecture="arm64" if agent.architecture == "aarch64" else agent.architecture,
        glibc_version=agent.glibc_version,
        agent_version=agent.agent_version,
        last_seen_at=agent.last_seen_at,
        last_ip=agent.last_ip,
        config_revision=agent.config_revision,
        created_at=agent.created_at,
        approved_at=agent.approved_at,
        revoked_at=agent.revoked_at,
        host=host,
        ssh_credentials_removed=ssh_credentials_removed,
    )


def enroll_agent(db: Session, payload: AgentEnrollInput, settings: Settings) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.agent_uuid == payload.agent_uuid))
    claim_hash = hash_agent_secret(payload.claim_token, settings.app_secret)
    values = payload.model_dump(
        exclude={"protocol_version", "agent_uuid", "claim_token"}
    )
    values["architecture"] = "arm64" if payload.architecture == "aarch64" else payload.architecture
    if agent and agent.status == "approved":
        return agent
    if not agent:
        agent = Agent(agent_uuid=payload.agent_uuid, claim_token_hash=claim_hash, **values)
        db.add(agent)
    else:
        for key, value in values.items():
            setattr(agent, key, value)
        agent.status = "pending"
        agent.claim_token_hash = claim_hash
        agent.secret_hash = None
        agent.pending_secret_encrypted = None
        agent.revoked_at = None
    db.commit()
    db.refresh(agent)
    return agent


def approve_agent(
    db: Session,
    agent_id: int,
    payload: AgentApproveInput,
    settings: Settings,
    cipher: SecretCipher,
) -> AgentOutput:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.status != "pending":
        raise HTTPException(status_code=409, detail="只有待审批 Agent 可以批准")
    ssh_removed = payload.mode == "bind"
    if payload.mode == "bind":
        host = db.get(Host, payload.host_id)
        if not host:
            raise HTTPException(status_code=404, detail="绑定主机不存在")
        if host.execution_mode == "agent":
            raise HTTPException(status_code=409, detail="主机已绑定 Agent")
        host.port = None
        host.username = agent.runtime_user
        host.auth_type = "agent"
        host.password_encrypted = None
        host.private_key_path = None
        host.execution_mode = "agent"
    else:
        host = Host(
            name=payload.host_name,
            hostname=agent.hostname,
            port=None,
            username=agent.runtime_user,
            auth_type="agent",
            execution_mode="agent",
            check_interval=60,
            enabled=True,
        )
        db.add(host)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="主机名称已存在")
    secret = generate_agent_secret()
    agent.host = host
    agent.status = "approved"
    agent.config_revision = 1
    agent.secret_hash = hash_agent_secret(secret, settings.app_secret)
    agent.pending_secret_encrypted = cipher.encrypt(secret)
    agent.approved_at = datetime.utcnow()
    agent.revoked_at = None
    db.commit()
    agent = get_agent(db, agent.id)
    return serialize_agent(agent, ssh_credentials_removed=ssh_removed)


def claim_agent_secret(
    db: Session,
    agent_uuid: str,
    claim_token: str,
    settings: Settings,
    cipher: SecretCipher,
) -> str:
    agent = db.scalar(select(Agent).where(Agent.agent_uuid == agent_uuid))
    if not agent or not agent.claim_token_hash:
        raise HTTPException(status_code=401, detail="领取凭据无效")
    if not verify_agent_secret(claim_token, agent.claim_token_hash, settings.app_secret):
        raise HTTPException(status_code=401, detail="领取凭据无效")
    if agent.status != "approved":
        raise HTTPException(status_code=409, detail="Agent 尚未批准")
    secret = cipher.decrypt(agent.pending_secret_encrypted)
    if not secret:
        raise HTTPException(status_code=401, detail="领取凭据已失效")
    return secret


def reject_agent(db: Session, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.status != "pending":
        raise HTTPException(status_code=409, detail="只有待审批 Agent 可以拒绝")
    agent.status = "rejected"
    agent.claim_token_hash = None
    agent.secret_hash = None
    agent.pending_secret_encrypted = None
    db.commit()
    return get_agent(db, agent.id)


def revoke_agent(db: Session, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    agent.status = "revoked"
    agent.claim_token_hash = None
    agent.secret_hash = None
    agent.pending_secret_encrypted = None
    agent.revoked_at = datetime.utcnow()
    db.commit()
    return get_agent(db, agent.id)


def rotate_agent_secret(db: Session, agent_id: int, settings: Settings) -> tuple:
    agent = db.get(Agent, agent_id)
    if not agent or agent.status != "approved":
        raise HTTPException(status_code=409, detail="只有已批准 Agent 可以轮换密钥")
    secret = generate_agent_secret()
    agent.secret_hash = hash_agent_secret(secret, settings.app_secret)
    agent.pending_secret_encrypted = None
    agent.claim_token_hash = None
    db.commit()
    return get_agent(db, agent.id), secret
