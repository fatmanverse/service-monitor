import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from ..dependencies import get_cipher, get_current_user, get_db, get_monitor, require_admin
from ..alert_targets import resolve_alert_configs
from ..agent_protocol import bump_agent_config_revision, queue_agent_command
from ..health_rules import HealthRuleError, validate_rule
from ..models import Host, ResourceGroup, Service, ServiceProbe, User, UserResourceGroup
from ..monitoring import MonitoringService
from ..probe_log_retention import list_probe_logs
from ..schemas import (
    ProbeItemResultOutput,
    ProbeLogPageOutput,
    ProbeResultOutput,
    ServiceCreate,
    ServiceOutput,
    ServiceProbeInput,
    ServiceUpdate,
)
from ..security import SecretCipher
from ..serializers import service_output
from ..start_commands import validate_start_user


router = APIRouter(prefix="/services", tags=["服务"])


def probe_result_output(result, service: Service) -> ProbeResultOutput:
    probes = []
    result_by_key = result.probe_results or {}
    for probe in service.probes:
        probe_result = result_by_key.get(probe.key)
        if not probe_result:
            continue
        probes.append(
            ProbeItemResultOutput(
                key=probe.key,
                name=probe.name,
                success=probe_result.success,
                message=probe_result.message,
                response_ms=probe_result.response_ms,
            )
        )
    return ProbeResultOutput(
        success=result.success,
        status=result.status,
        message=result.message,
        response_ms=result.response_ms,
        restarted=result.restarted,
        probes=probes,
    )


def service_load_options():
    return (
        joinedload(Service.host),
        joinedload(Service.resource_group),
        selectinload(Service.probes),
        selectinload(Service.alert_configs),
    )


def visible_service_query(user: User):
    query = select(Service).options(*service_load_options()).order_by(Service.name)
    if not user.is_admin:
        query = query.join(
            UserResourceGroup,
            UserResourceGroup.resource_group_id == Service.resource_group_id,
        ).where(UserResourceGroup.user_id == user.id)
    return query


def get_visible_service(db: Session, service_id: int, user: User) -> Service:
    service = db.scalar(visible_service_query(user).where(Service.id == service_id))
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    return service


def validate_configuration(
    probes: List[ServiceProbeInput],
    health_rule: dict,
    auto_restart: bool,
    start_command: str,
    start_user: Optional[str] = None,
    existing_by_key=None,
):
    keys = [probe.key for probe in probes]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="探活项规则标识不能重复")
    if not any(probe.enabled for probe in probes):
        raise HTTPException(status_code=422, detail="至少需要一个启用的探活项")
    enabled_keys = {probe.key for probe in probes if probe.enabled}
    try:
        validate_rule(health_rule, enabled_keys)
    except HealthRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if auto_restart and not start_command:
        raise HTTPException(status_code=422, detail="自动拉起必须提供服务启动命令")
    if start_user and not start_command:
        raise HTTPException(status_code=422, detail="启动用户必须提供服务启动命令")
    try:
        validate_start_user(start_user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    for probe in probes:
        existing = existing_by_key.get(probe.key) if existing_by_key else None
        retained_secret = (
            existing.auth_secret_encrypted
            if existing and existing.auth_type == probe.auth_type
            else None
        )
        if probe.auth_type == "basic" and (
            not probe.auth_username or not (probe.auth_secret or retained_secret)
        ):
            raise HTTPException(status_code=422, detail=f"探活项“{probe.name}”的 Basic 认证缺少用户名或密钥")
        if probe.auth_type == "bearer" and not (probe.auth_secret or retained_secret):
            raise HTTPException(status_code=422, detail=f"探活项“{probe.name}”的 Bearer 认证缺少密钥")


def make_probe(payload: ServiceProbeInput, cipher: SecretCipher, existing: ServiceProbe = None) -> ServiceProbe:
    probe = ServiceProbe(
        key=payload.key,
        name=payload.name,
        probe_type=payload.probe_type,
        process_pattern=payload.process_pattern,
        url=str(payload.url) if payload.url else None,
        headers_json=json.dumps(payload.headers, ensure_ascii=False),
        body_json=json.dumps(payload.body, ensure_ascii=False) if payload.body is not None else None,
        auth_type=payload.auth_type,
        auth_username=payload.auth_username,
        auth_secret_encrypted=cipher.encrypt(payload.auth_secret)
        or (existing.auth_secret_encrypted if existing and existing.auth_type == payload.auth_type else None),
        expected_status=payload.expected_status,
        timeout_seconds=payload.timeout_seconds,
        enabled=payload.enabled,
    )
    if probe.probe_type == "process":
        probe.url = None
        probe.headers_json = "{}"
        probe.body_json = None
        probe.auth_type = "none"
        probe.auth_username = None
        probe.auth_secret_encrypted = None
    elif probe.auth_type == "none":
        probe.auth_username = None
        probe.auth_secret_encrypted = None
    elif probe.auth_type == "bearer":
        probe.auth_username = None
    return probe


def sync_legacy_probe_fields(service: Service, probe: ServiceProbe) -> None:
    service.probe_type = probe.probe_type
    service.process_pattern = probe.process_pattern
    service.url = probe.url
    service.headers_json = probe.headers_json
    service.body_json = probe.body_json
    service.auth_type = probe.auth_type
    service.auth_username = probe.auth_username
    service.auth_secret_encrypted = probe.auth_secret_encrypted
    service.expected_status = probe.expected_status
    service.timeout_seconds = probe.timeout_seconds


@router.get("", response_model=List[ServiceOutput])
def list_services(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [service_output(service) for service in db.scalars(visible_service_query(current_user)).unique().all()]


@router.get("/{service_id}", response_model=ServiceOutput)
def get_service(service_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service_output(get_visible_service(db, service_id, current_user))


@router.post("", response_model=ServiceOutput, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    host = db.get(Host, payload.host_id)
    if not host:
        raise HTTPException(status_code=404, detail="主机不存在")
    if not db.get(ResourceGroup, payload.resource_group_id):
        raise HTTPException(status_code=404, detail="资源组不存在")
    validate_configuration(
        payload.probes,
        payload.health_rule,
        payload.auto_restart,
        payload.start_command,
        payload.start_user,
    )
    alert_configs = resolve_alert_configs(db, payload.alert_config_ids)
    probes = [make_probe(probe, cipher) for probe in payload.probes]
    service = Service(
        host_id=payload.host_id,
        resource_group_id=payload.resource_group_id,
        name=payload.name,
        health_rule_json=json.dumps(payload.health_rule, ensure_ascii=False),
        start_command=payload.start_command,
        start_user=payload.start_user,
        check_interval=payload.check_interval,
        enabled=payload.enabled,
        auto_restart=payload.auto_restart,
        alert_configs=alert_configs,
        probes=probes,
    )
    sync_legacy_probe_fields(service, probes[0])
    db.add(service)
    bump_agent_config_revision(db, host.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="服务名称或探活项标识已存在")
    service = db.scalar(select(Service).options(*service_load_options()).where(Service.id == service.id))
    return service_output(service)


@router.put("/{service_id}", response_model=ServiceOutput)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    cipher: SecretCipher = Depends(get_cipher),
    _admin: User = Depends(require_admin),
):
    service = db.scalar(select(Service).options(*service_load_options()).where(Service.id == service_id))
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    original_host_id = service.host_id
    values = payload.model_dump(exclude_unset=True, exclude={"probes", "health_rule", "alert_config_ids"})
    if "host_id" in values and not db.get(Host, values["host_id"]):
        raise HTTPException(status_code=404, detail="主机不存在")
    if "resource_group_id" in values and not db.get(ResourceGroup, values["resource_group_id"]):
        raise HTTPException(status_code=404, detail="资源组不存在")
    effective_probes = payload.probes or [
        ServiceProbeInput(
            key=probe.key,
            name=probe.name,
            probe_type=probe.probe_type,
            process_pattern=probe.process_pattern,
            url=probe.url,
            headers=json.loads(probe.headers_json or "{}"),
            body=json.loads(probe.body_json) if probe.body_json else None,
            auth_type=probe.auth_type,
            auth_username=probe.auth_username,
            auth_secret="retained" if probe.auth_secret_encrypted else None,
            expected_status=probe.expected_status,
            timeout_seconds=probe.timeout_seconds,
            enabled=probe.enabled,
        ) for probe in service.probes
    ]
    effective_rule = (
        payload.health_rule
        if payload.health_rule is not None
        else json.loads(service.health_rule_json)
    )
    effective_auto_restart = values.get("auto_restart", service.auto_restart)
    effective_start_command = values.get("start_command", service.start_command)
    effective_start_user = values.get("start_user", service.start_user)
    validate_configuration(
        effective_probes,
        effective_rule,
        effective_auto_restart,
        effective_start_command,
        effective_start_user,
        {probe.key: probe for probe in service.probes},
    )
    for key, value in values.items():
        setattr(service, key, value)
    if payload.health_rule is not None:
        service.health_rule_json = json.dumps(payload.health_rule, ensure_ascii=False)
    if payload.probes is not None:
        existing_by_key = {probe.key: probe for probe in service.probes}
        for probe in list(service.probes):
            db.delete(probe)
        db.flush()
        replacement_probes = [make_probe(probe, cipher, existing_by_key.get(probe.key)) for probe in payload.probes]
        service.probes.extend(replacement_probes)
        sync_legacy_probe_fields(service, replacement_probes[0])
    if payload.alert_config_ids is not None:
        service.alert_configs = resolve_alert_configs(db, payload.alert_config_ids)
    bump_agent_config_revision(db, original_host_id)
    if service.host_id != original_host_id:
        bump_agent_config_revision(db, service.host_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="服务名称或探活项标识已存在")
    service = db.scalar(select(Service).options(*service_load_options()).where(Service.id == service_id))
    return service_output(service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    bump_agent_config_revision(db, service.host_id)
    db.delete(service)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{service_id}/probe", response_model=ProbeResultOutput)
def probe_service(
    service_id: int,
    request: Request,
    db: Session = Depends(get_db),
    monitor: MonitoringService = Depends(get_monitor),
    current_user: User = Depends(get_current_user),
):
    service = get_visible_service(db, service_id, current_user)
    if service.host.execution_mode == "agent":
        command = queue_agent_command(
            db,
            service,
            "probe_service",
            request.app.state.settings.agent_offline_seconds,
        )
        return ProbeResultOutput(
            mode="queued",
            success=None,
            status=service.status,
            message="已加入 Agent 命令队列",
            command_id=command.command_id,
            command_status=command.status,
        )
    result = monitor.check_service(db, service, allow_restart=False)
    return probe_result_output(result, service)


@router.post("/{service_id}/restart", response_model=ProbeResultOutput)
def restart_service(
    service_id: int,
    request: Request,
    db: Session = Depends(get_db),
    monitor: MonitoringService = Depends(get_monitor),
    _admin: User = Depends(require_admin),
):
    service = db.scalar(select(Service).options(*service_load_options()).where(Service.id == service_id))
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    if service.host.execution_mode == "agent":
        command = queue_agent_command(
            db,
            service,
            "restart_service",
            request.app.state.settings.agent_offline_seconds,
        )
        return ProbeResultOutput(
            mode="queued",
            success=None,
            status=service.status,
            message="已加入 Agent 命令队列",
            command_id=command.command_id,
            command_status=command.status,
        )
    result = monitor.restart_and_check(db, service)
    return probe_result_output(result, service)


@router.get("/{service_id}/logs", response_model=ProbeLogPageOutput)
def service_logs(
    service_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_visible_service(db, service_id, current_user)
    try:
        page = list_probe_logs(db, service_id, limit, cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProbeLogPageOutput(items=page.items, next_cursor=page.next_cursor)
