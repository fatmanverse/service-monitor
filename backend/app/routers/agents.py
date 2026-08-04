from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..agent_schemas import (
    AgentApproveInput,
    AgentOutput,
    AgentSecretRotationOutput,
)
from ..agent_service import (
    approve_agent,
    get_agent,
    list_agents,
    reject_agent,
    revoke_agent,
    rotate_agent_secret,
    serialize_agent,
)
from ..dependencies import get_cipher, get_db, require_admin
from ..models import User
from ..security import SecretCipher


router = APIRouter(prefix="/agents", tags=["Agent 管理"])


@router.get("", response_model=List[AgentOutput])
def get_agents(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return [serialize_agent(agent) for agent in list_agents(db)]


@router.post("/{agent_id}/approve", response_model=AgentOutput)
def approve(
    agent_id: int,
    payload: AgentApproveInput,
    request: Request,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    return approve_agent(db, agent_id, payload, request.app.state.settings, cipher)


@router.post("/{agent_id}/reject", response_model=AgentOutput)
def reject(
    agent_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return serialize_agent(reject_agent(db, agent_id))


@router.post("/{agent_id}/revoke", response_model=AgentOutput)
def revoke(
    agent_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return serialize_agent(revoke_agent(db, agent_id))


@router.post("/{agent_id}/rotate-secret", response_model=AgentSecretRotationOutput)
def rotate_secret(
    agent_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    agent, secret = rotate_agent_secret(db, agent_id, request.app.state.settings)
    return AgentSecretRotationOutput(agent=serialize_agent(agent), agent_secret=secret)
