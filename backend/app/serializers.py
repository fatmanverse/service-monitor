import json

from .models import Service, ServiceProbe
from .schemas import AlertConfigReference, ServiceOutput, ServiceProbeOutput


def probe_output(probe: ServiceProbe) -> ServiceProbeOutput:
    return ServiceProbeOutput(
        id=probe.id,
        key=probe.key,
        name=probe.name,
        probe_type=probe.probe_type,
        process_pattern=probe.process_pattern,
        url=probe.url,
        headers=json.loads(probe.headers_json or "{}"),
        body=json.loads(probe.body_json) if probe.body_json else None,
        auth_type=probe.auth_type,
        auth_username=probe.auth_username,
        expected_status=probe.expected_status,
        timeout_seconds=probe.timeout_seconds,
        enabled=probe.enabled,
        last_success=probe.last_success,
        last_checked_at=probe.last_checked_at,
        last_error=probe.last_error,
        last_response_ms=probe.last_response_ms,
    )


def service_output(service: Service) -> ServiceOutput:
    return ServiceOutput(
        id=service.id,
        host_id=service.host_id,
        host_name=service.host.name,
        resource_group_id=service.resource_group_id,
        resource_group_name=service.resource_group.name,
        name=service.name,
        probes=[probe_output(probe) for probe in service.probes],
        health_rule=json.loads(service.health_rule_json),
        start_command=service.start_command,
        check_interval=service.check_interval,
        enabled=service.enabled,
        auto_restart=service.auto_restart,
        alert_configs=[
            AlertConfigReference(id=config.id, name=config.name, enabled=config.enabled)
            for config in service.alert_configs
        ],
        status=service.status,
        last_checked_at=service.last_checked_at,
        last_error=service.last_error,
        last_response_ms=service.last_response_ms,
        next_check_at=service.next_check_at,
        created_at=service.created_at,
    )
