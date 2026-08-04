from sqlalchemy import func, select

from agent_test_helpers import approve_agent
from app.models import ProbeLog, Service
from test_api import create_service


def test_agent_report_is_idempotent_and_updates_latest_state(
    client, admin_headers, agent_rpc
):
    approved, agent_headers = approve_agent(client, admin_headers)
    service = create_service(
        client,
        admin_headers,
        approved["host"]["id"],
        name="agent-report-service",
    )
    report = {
        "protocol_version": 1,
        "reports": [
            {
                "report_id": "report-0001",
                "report_sequence": 1,
                "service_id": service["id"],
                "success": False,
                "message": "HTTP 连接失败",
                "response_ms": 25,
                "restarted": False,
                "occurred_at": "2026-08-04T00:00:00Z",
                "probes": [
                    {
                        "key": "http-main",
                        "success": False,
                        "message": "HTTP 连接失败",
                        "response_ms": 25,
                    }
                ],
            }
        ],
    }

    first, first_context = agent_rpc.report(report, agent_headers)
    second, second_context = agent_rpc.report(report, agent_headers)
    assert first_context.code.name == "OK", first_context.details
    assert second_context.code.name == "OK", second_context.details
    assert first.accepted == 1
    assert second.duplicates == 1

    with client.app.state.database.session_factory() as db:
        stored = db.get(Service, service["id"])
        count = db.scalar(
            select(func.count(ProbeLog.id)).where(ProbeLog.service_id == service["id"])
        )
        assert stored.status == "offline"
        assert stored.last_error == "HTTP 连接失败"
        assert count == 1


def test_agent_cannot_report_another_hosts_service(client, admin_headers, agent_rpc):
    from test_api import create_host

    _approved, agent_headers = approve_agent(client, admin_headers)
    ssh_host = create_host(client, admin_headers, name="unrelated-ssh")
    foreign_service = create_service(client, admin_headers, ssh_host["id"], name="foreign")

    _response, context = agent_rpc.report(
        {
            "protocol_version": 1,
            "reports": [
                {
                    "report_id": "foreign-report",
                    "report_sequence": 1,
                    "service_id": foreign_service["id"],
                    "success": True,
                    "message": "ok",
                    "occurred_at": "2026-08-04T00:00:00Z",
                    "probes": [],
                }
            ],
        },
        agent_headers,
    )
    assert context.code.name == "PERMISSION_DENIED"
