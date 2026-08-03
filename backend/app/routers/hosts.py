from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..dependencies import get_cipher, get_db, get_monitor, require_admin
from ..alert_targets import resolve_alert_configs
from ..models import Host, User
from ..monitoring import MonitoringService
from ..schemas import HostCreate, HostOutput, HostUpdate, ProbeResultOutput
from ..serializers import host_output
from ..security import SecretCipher
from ..validation import validate_host_auth


router = APIRouter(prefix="/hosts", tags=["主机"])


@router.get("", response_model=List[HostOutput])
def list_hosts(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    hosts = db.scalars(
        select(Host).options(selectinload(Host.alert_configs)).order_by(Host.name)
    ).all()
    return [host_output(host) for host in hosts]


@router.post("", response_model=HostOutput, status_code=status.HTTP_201_CREATED)
def create_host(
    payload: HostCreate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    host = Host(
        name=payload.name,
        hostname=payload.hostname,
        port=payload.port,
        username=payload.username,
        auth_type=payload.auth_type,
        password_encrypted=None,
        private_key_path=payload.private_key_path,
        check_interval=payload.check_interval,
        enabled=payload.enabled,
    )
    db.add(host)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="主机名称已存在")
    if payload.password:
        host.password_encrypted = cipher.encrypt(payload.password)
    if host.auth_type == "password":
        host.private_key_path = None
    else:
        host.password_encrypted = None
    validate_host_auth(host.auth_type, host.password_encrypted, host.private_key_path)
    host.alert_configs = resolve_alert_configs(db, payload.alert_config_ids)
    db.commit()
    host = db.scalar(
        select(Host).options(selectinload(Host.alert_configs)).where(Host.id == host.id)
    )
    return host_output(host)


@router.put("/{host_id}", response_model=HostOutput)
def update_host(
    host_id: int,
    payload: HostUpdate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    host = db.get(Host, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    values = payload.model_dump(exclude_unset=True, exclude={"alert_config_ids"})
    password = values.pop("password", None)
    for key, value in values.items():
        setattr(host, key, value)
    if password:
        host.password_encrypted = cipher.encrypt(password)
    if host.auth_type == "password":
        host.private_key_path = None
    else:
        host.password_encrypted = None
    validate_host_auth(host.auth_type, host.password_encrypted, host.private_key_path)
    if payload.alert_config_ids is not None:
        host.alert_configs = resolve_alert_configs(db, payload.alert_config_ids)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="主机名称已存在")
    host = db.scalar(select(Host).options(selectinload(Host.alert_configs)).where(Host.id == host_id))
    return host_output(host)


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(
    host_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    host = db.get(Host, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    db.delete(host)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{host_id}/probe", response_model=ProbeResultOutput)
def probe_host(
    host_id: int,
    db: Session = Depends(get_db),
    monitor: MonitoringService = Depends(get_monitor),
    _admin: User = Depends(require_admin),
):
    host = db.get(Host, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    result = monitor.check_host(db, host)
    return ProbeResultOutput(success=result.success, status=result.status, message=result.message, response_ms=result.response_ms)
