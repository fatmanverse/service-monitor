from app.models import Agent, Host, Service


ENROLLMENT = {
    "protocol_version": 1,
    "agent_uuid": "7f49d1e1-ff52-4c1d-9e1c-1cce9ae7b101",
    "claim_token": "claim-token-with-at-least-thirty-two-random-characters",
    "hostname": "agent-node-01",
    "runtime_user": "root",
    "os_release": "Ubuntu 22.04",
    "architecture": "x86_64",
    "glibc_version": "2.35",
    "agent_version": "0.1.0",
}


def enroll(agent_rpc, payload=None):
    response, context = agent_rpc.enroll(payload or ENROLLMENT)
    assert context.code.name == "OK", context.details
    return response


def test_agent_requires_approval_then_claims_secret_until_first_heartbeat(
    client, admin_headers, agent_rpc
):
    enrollment = enroll(agent_rpc)
    assert enrollment.status == "pending"

    pending_claim, pending_context = agent_rpc.claim(
        {
            "protocol_version": 1,
            "agent_uuid": ENROLLMENT["agent_uuid"],
            "claim_token": ENROLLMENT["claim_token"],
        }
    )
    assert pending_context.code.name == "FAILED_PRECONDITION"

    agents = client.get("/api/agents", headers=admin_headers)
    assert agents.status_code == 200
    agent_id = agents.json()[0]["id"]
    approved = client.post(
        f"/api/agents/{agent_id}/approve",
        headers=admin_headers,
        json={"mode": "new", "host_name": "agent-managed-node"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["host"]["execution_mode"] == "agent"

    claim_payload = {
        "protocol_version": 1,
        "agent_uuid": ENROLLMENT["agent_uuid"],
        "claim_token": ENROLLMENT["claim_token"],
    }
    first_claim, first_context = agent_rpc.claim(claim_payload)
    second_claim, second_context = agent_rpc.claim(claim_payload)
    assert first_context.code.name == "OK", first_context.details
    assert second_context.code.name == "OK", second_context.details
    assert first_claim.agent_secret == second_claim.agent_secret
    with client.app.state.database.session_factory() as db:
        stored = db.get(Agent, agent_id)
        assert stored.secret_hash != first_claim.agent_secret
        assert stored.pending_secret_encrypted != first_claim.agent_secret

    auth_headers = {
        "X-Agent-ID": ENROLLMENT["agent_uuid"],
        "Authorization": f"Bearer {first_claim.agent_secret}",
    }
    heartbeat, heartbeat_context = agent_rpc.heartbeat(
        {"protocol_version": 1, "config_revision": 0, "outbox_size": 0},
        tuple((key.lower(), value) for key, value in auth_headers.items()),
    )
    assert heartbeat_context.code.name == "OK", heartbeat_context.details

    consumed_claim, consumed_context = agent_rpc.claim(claim_payload)
    assert consumed_context.code.name == "UNAUTHENTICATED"

    revoked = client.post(
        f"/api/agents/{agent_id}/revoke",
        headers=admin_headers,
    )
    assert revoked.status_code == 200
    _heartbeat, revoked_context = agent_rpc.heartbeat(
        {"protocol_version": 1, "config_revision": 0, "outbox_size": 0},
        tuple((key.lower(), value) for key, value in auth_headers.items()),
    )
    assert revoked_context.code.name == "UNAUTHENTICATED"


def test_binding_existing_host_retires_ssh_data_and_preserves_services(
    client, admin_headers, agent_rpc
):
    from test_api import create_host, create_service

    host_data = create_host(client, admin_headers, name="existing-ssh-node")
    service_data = create_service(client, admin_headers, host_data["id"])
    enroll(agent_rpc)
    agent_id = client.get("/api/agents", headers=admin_headers).json()[0]["id"]

    approved = client.post(
        f"/api/agents/{agent_id}/approve",
        headers=admin_headers,
        json={"mode": "bind", "host_id": host_data["id"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["ssh_credentials_removed"] is True

    with client.app.state.database.session_factory() as db:
        host = db.get(Host, host_data["id"])
        agent = db.get(Agent, agent_id)
        service = db.get(Service, service_data["id"])
        assert host.execution_mode == "agent"
        assert host.auth_type == "agent"
        assert host.port is None
        assert host.username == ENROLLMENT["runtime_user"]
        assert host.password_encrypted is None
        assert host.private_key_path is None
        assert agent.host_id == host.id
        assert service.host_id == host.id
        assert service.resource_group_id == service_data["resource_group_id"]


def test_enrollment_updates_one_pending_record(client, admin_headers, agent_rpc):
    enroll(agent_rpc)
    changed = {**ENROLLMENT, "agent_version": "0.1.1", "os_release": "Debian 12"}
    enroll(agent_rpc, changed)

    agents = client.get("/api/agents", headers=admin_headers).json()
    assert len(agents) == 1
    assert agents[0]["agent_version"] == "0.1.1"
    assert agents[0]["os_release"] == "Debian 12"
