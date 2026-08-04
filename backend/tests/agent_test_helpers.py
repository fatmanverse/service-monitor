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


def approve_agent(client, admin_headers, agent_rpc=None, host_name="agent-node"):
    if agent_rpc is None:
        from conftest import AgentRpcClient

        agent_rpc = AgentRpcClient(client.app)
    enrolled, context = agent_rpc.enroll(ENROLLMENT)
    assert context.code.name == "OK", context.details
    assert enrolled.status == "pending"
    agent = client.get("/api/agents", headers=admin_headers).json()[0]
    approved = client.post(
        f"/api/agents/{agent['id']}/approve",
        headers=admin_headers,
        json={"mode": "new", "host_name": host_name},
    )
    assert approved.status_code == 200, approved.text
    claim, context = agent_rpc.claim(
        {
            "protocol_version": 1,
            "agent_uuid": ENROLLMENT["agent_uuid"],
            "claim_token": ENROLLMENT["claim_token"],
        }
    )
    assert context.code.name == "OK", context.details
    metadata = (
        ("x-agent-id", ENROLLMENT["agent_uuid"]),
        ("authorization", f"Bearer {claim.agent_secret}"),
    )
    _heartbeat, context = agent_rpc.heartbeat(
        {"protocol_version": 1, "config_revision": 0, "outbox_size": 0},
        metadata,
    )
    assert context.code.name == "OK", context.details
    return approved.json(), metadata
