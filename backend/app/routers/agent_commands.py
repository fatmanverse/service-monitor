import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent_schemas import AgentCommandStatusOutput
from ..authorization import service_visibility_filter
from ..dependencies import get_current_user, get_db
from ..models import AgentCommand, Service, User


router = APIRouter(prefix="/agent-commands", tags=["Agent 命令"])


@router.get("/{command_id}", response_model=AgentCommandStatusOutput)
def get_command(
    command_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    command = db.get(AgentCommand, command_id)
    if not command:
        raise HTTPException(status_code=404, detail="Agent 命令不存在")
    if not current_user.is_admin:
        visible = db.scalar(
            select(Service.id).where(
                Service.id == command.service_id,
                service_visibility_filter(current_user),
            )
        )
        if not visible:
            raise HTTPException(status_code=404, detail="Agent 命令不存在")
    return AgentCommandStatusOutput(
        command_id=command.command_id,
        service_id=command.service_id,
        command_type=command.command_type,
        status=command.status,
        result=json.loads(command.result_json) if command.result_json else None,
        created_at=command.created_at,
        claimed_at=command.claimed_at,
        finished_at=command.finished_at,
        expires_at=command.expires_at,
    )
