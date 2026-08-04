from agent_test_helpers import approve_agent
from test_api import create_service


def test_agent_receives_only_bound_host_configuration_and_commands(
    client, admin_headers, agent_rpc
):
    approved, agent_headers = approve_agent(client, admin_headers)
    host_id = approved["host"]["id"]
    service = create_service(client, admin_headers, host_id, name="agent-service")

    config, context = agent_rpc.config(agent_headers)
    assert context.code.name == "OK", context.details
    assert config.host_id == host_id
    assert [item.id for item in config.services] == [service["id"]]
    assert config.services[0].health_rule_json == '{"probe": "http-main"}'

    queued = client.post(
        f"/api/services/{service['id']}/probe",
        headers=admin_headers,
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["mode"] == "queued"
    assert queued.json()["success"] is None
    assert queued.json()["command_status"] == "pending"

    heartbeat, context = agent_rpc.heartbeat(
        {"protocol_version": 1, "config_revision": 0, "outbox_size": 0},
        agent_headers,
    )
    assert context.code.name == "OK", context.details
    assert heartbeat.commands[0].command_id == queued.json()["command_id"]


def test_agent_host_is_excluded_from_ssh_scheduler(
    client, admin_headers, agent_rpc, monkeypatch
):
    approved, _agent_headers = approve_agent(client, admin_headers)
    create_service(client, admin_headers, approved["host"]["id"], name="agent-service")
    monitor = client.app.state.monitoring

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Agent 主机不得进入 SSH 调度")

    monkeypatch.setattr(monitor, "check_host", unexpected)
    monkeypatch.setattr(monitor, "check_service", unexpected)
    client.app.state.scheduler.run_due_checks()


def test_agent_host_rejects_manual_ssh_probe(client, admin_headers, agent_rpc, monkeypatch):
    approved, _metadata = approve_agent(client, admin_headers, agent_rpc)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Agent 主机不得进入 SSH 探活")

    monkeypatch.setattr(client.app.state.monitoring, "check_host", unexpected)
    response = client.post(
        f"/api/hosts/{approved['host']['id']}/probe",
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Agent 主机状态由心跳维护"
