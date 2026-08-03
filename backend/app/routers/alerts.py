from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import get_cipher, get_db, get_monitor, require_admin
from ..models import AlertConfig, HostAlertConfig, ServiceAlertConfig, User
from ..monitoring import MonitoringService
from ..schemas import AlertConfigCreate, AlertConfigOutput, AlertConfigUpdate, ProbeResultOutput
from ..security import SecretCipher


router = APIRouter(prefix="/alerts", tags=["告警"])


def alert_output(db: Session, config: AlertConfig) -> AlertConfigOutput:
    service_count = db.scalar(
        select(func.count(ServiceAlertConfig.service_id)).where(
            ServiceAlertConfig.alert_config_id == config.id
        )
    ) or 0
    host_count = db.scalar(
        select(func.count(HostAlertConfig.host_id)).where(
            HostAlertConfig.alert_config_id == config.id
        )
    ) or 0
    return AlertConfigOutput(
        id=config.id,
        name=config.name,
        enabled=config.enabled,
        webhook_configured=bool(config.webhook_encrypted),
        service_count=service_count,
        host_count=host_count,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("", response_model=List[AlertConfigOutput])
def list_alerts(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    configs = db.scalars(select(AlertConfig).order_by(AlertConfig.name)).all()
    return [alert_output(db, config) for config in configs]


@router.post("", response_model=AlertConfigOutput, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertConfigCreate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    config = AlertConfig(
        name=payload.name,
        enabled=payload.enabled,
        webhook_encrypted=cipher.encrypt(str(payload.webhook_url)),
    )
    db.add(config)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="告警配置名称已存在")
    db.refresh(config)
    return alert_output(db, config)


@router.put("/{config_id}", response_model=AlertConfigOutput)
def update_alert(
    config_id: int,
    payload: AlertConfigUpdate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    config = db.get(AlertConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="告警配置不存在")
    values = payload.model_dump(exclude_unset=True, exclude={"webhook_url"})
    for key, value in values.items():
        setattr(config, key, value)
    if payload.webhook_url:
        config.webhook_encrypted = cipher.encrypt(str(payload.webhook_url))
    if config.enabled and not config.webhook_encrypted:
        raise HTTPException(status_code=422, detail="启用告警前必须配置 Webhook")
    config.updated_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="告警配置名称已存在")
    db.refresh(config)
    return alert_output(db, config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    config_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    config = db.get(AlertConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="告警配置不存在")
    db.delete(config)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{config_id}/test", response_model=ProbeResultOutput)
def test_alert(
    config_id: int,
    db: Session = Depends(get_db),
    monitor: MonitoringService = Depends(get_monitor),
    _admin: User = Depends(require_admin),
):
    config = db.get(AlertConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="告警配置不存在")
    result = monitor.test_alert(config)
    return ProbeResultOutput(
        success=result.success,
        status=result.status,
        message=result.message,
        response_ms=result.response_ms,
    )
