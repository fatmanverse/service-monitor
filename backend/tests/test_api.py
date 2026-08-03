def create_host(client, headers, name="node-a"):
    response = client.post(
        "/api/hosts",
        headers=headers,
        json={
            "name": name,
            "hostname": "127.0.0.1",
            "port": 22,
            "username": "ops",
            "auth_type": "password",
            "password": "secret",
            "check_interval": 60,
            "enabled": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_group(client, headers, name="default-group"):
    response = client.post(
        "/api/resource-groups",
        headers=headers,
        json={"name": name, "description": "test group"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_service(client, headers, host_id, name="api-service", group_id=None, alert_config_ids=None):
    group = create_group(client, headers, f"{name}-group") if group_id is None else None
    response = client.post(
        "/api/services",
        headers=headers,
        json={
            "host_id": host_id,
            "resource_group_id": group_id or group["id"],
            "name": name,
            "probes": [
                {
                    "key": "http-main",
                    "name": "主地址",
                    "probe_type": "get",
                    "url": "http://127.0.0.1:9999/health",
                    "headers": {"X-Monitor": "true"},
                    "auth_type": "none",
                    "enabled": True,
                }
            ],
            "health_rule": {"probe": "http-main"},
            "check_interval": 60,
            "enabled": True,
            "auto_restart": False,
            "alert_config_ids": alert_config_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_can_create_host_and_service(client, admin_headers):
    host = create_host(client, admin_headers)
    service = create_service(client, admin_headers, host["id"])

    assert service["host_id"] == host["id"]
    assert service["status"] == "unknown"
    assert service["probes"][0]["headers"] == {"X-Monitor": "true"}
    assert service["health_rule"] == {"probe": "http-main"}
    assert service["alert_configs"] == []


def create_alert(client, headers, name):
    response = client.post(
        "/api/alerts",
        headers=headers,
        json={
            "name": name,
            "enabled": True,
            "webhook_url": f"https://open.feishu.cn/open-apis/bot/v2/hook/{name}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_service_can_select_multiple_alert_configs(client, admin_headers):
    first = create_alert(client, admin_headers, "值班群")
    second = create_alert(client, admin_headers, "业务群")
    host = create_host(client, admin_headers)
    service = create_service(
        client,
        admin_headers,
        host["id"],
        alert_config_ids=[first["id"], second["id"]],
    )

    assert {item["id"] for item in service["alert_configs"]} == {first["id"], second["id"]}
    assert client.get("/api/alerts", headers=admin_headers).json()[0]["service_count"] == 1

    deleted = client.delete(f"/api/alerts/{first['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    unchanged = client.get(f"/api/services/{service['id']}", headers=admin_headers).json()
    assert [item["id"] for item in unchanged["alert_configs"]] == [second["id"]]


def test_service_rejects_unknown_alert_config(client, admin_headers):
    host = create_host(client, admin_headers)
    response = client.post(
        "/api/services",
        headers=admin_headers,
        json={
            "host_id": host["id"],
            "resource_group_id": create_group(client, admin_headers)["id"],
            "name": "invalid-alert",
            "probes": [
                {
                    "key": "http-main",
                    "name": "主地址",
                    "probe_type": "get",
                    "url": "http://127.0.0.1/health",
                    "enabled": True,
                }
            ],
            "health_rule": {"probe": "http-main"},
            "alert_config_ids": [999999],
        },
    )

    assert response.status_code == 422


def test_status_alert_attempts_every_config(monkeypatch):
    from types import SimpleNamespace

    from app.monitoring import MonitoringService, ProbeResult

    monitor = object.__new__(MonitoringService)
    attempted = []

    def fake_post(config, _text):
        attempted.append(config.name)
        return ProbeResult(config.name != "失败群", "发送失败" if config.name == "失败群" else "发送成功")

    monkeypatch.setattr(monitor, "_post_feishu", fake_post)
    service = SimpleNamespace(
        name="订单服务",
        host=SimpleNamespace(name="节点一", hostname="10.0.0.1"),
    )
    configs = [SimpleNamespace(name="失败群"), SimpleNamespace(name="成功群")]

    result = monitor._send_status_alert(
        configs,
        service,
        "online",
        ProbeResult(False, "进程不存在"),
    )

    assert attempted == ["失败群", "成功群"]
    assert result.success is False
    assert "失败群" in result.message


def test_interval_below_sixty_seconds_is_rejected(client, admin_headers):
    response = client.post(
        "/api/hosts",
        headers=admin_headers,
        json={
            "name": "too-fast",
            "hostname": "localhost",
            "port": 22,
            "username": "ops",
            "auth_type": "key",
            "private_key_path": "/tmp/test-key",
            "check_interval": 30,
            "enabled": True,
        },
    )

    assert response.status_code == 422


def test_non_admin_only_sees_granted_services(client, admin_headers):
    host = create_host(client, admin_headers)
    visible = create_service(client, admin_headers, host["id"], "visible")
    create_service(client, admin_headers, host["id"], "hidden")

    user_response = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": "viewer", "password": "viewer-pass", "is_admin": False},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]
    grant_response = client.put(
        f"/api/users/{user_id}/resource-groups",
        headers=admin_headers,
        json={"resource_group_ids": [visible["resource_group_id"]]},
    )
    assert grant_response.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "viewer-pass"},
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/services", headers=viewer_headers)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["visible"]
    assert client.get("/api/users", headers=viewer_headers).status_code == 403


def test_deleting_host_cascades_services_and_grants(client, admin_headers):
    host = create_host(client, admin_headers)
    service = create_service(client, admin_headers, host["id"])
    user = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": "viewer", "password": "viewer-pass", "is_admin": False},
    ).json()
    client.put(
        f"/api/users/{user['id']}/resource-groups",
        headers=admin_headers,
        json={"resource_group_ids": [service["resource_group_id"]]},
    )

    response = client.delete(f"/api/hosts/{host['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/api/services/{service['id']}", headers=admin_headers).status_code == 404
    grants = client.get(f"/api/users/{user['id']}/resource-groups", headers=admin_headers)
    assert grants.status_code == 200
    assert [item["id"] for item in grants.json()] == [service["resource_group_id"]]


def test_health_rule_requires_each_enabled_probe_exactly_once(client, admin_headers):
    host = create_host(client, admin_headers)
    group = create_group(client, admin_headers)
    response = client.post(
        "/api/services",
        headers=admin_headers,
        json={
            "host_id": host["id"],
            "resource_group_id": group["id"],
            "name": "invalid-rule",
            "probes": [
                {"key": "a", "name": "A", "probe_type": "get", "url": "http://127.0.0.1/a", "enabled": True},
                {"key": "b", "name": "B", "probe_type": "get", "url": "http://127.0.0.1/b", "enabled": True},
            ],
            "health_rule": {"probe": "a"},
            "check_interval": 60,
        },
    )
    assert response.status_code == 422


def test_service_update_rejects_empty_health_rule(client, admin_headers):
    host = create_host(client, admin_headers)
    service = create_service(client, admin_headers, host["id"])

    response = client.put(
        f"/api/services/{service['id']}",
        headers=admin_headers,
        json={"health_rule": {}},
    )

    assert response.status_code == 422
    unchanged = client.get(f"/api/services/{service['id']}", headers=admin_headers)
    assert unchanged.json()["health_rule"] == {"probe": "http-main"}


def test_nested_health_rule_evaluation():
    from app.health_rules import evaluate_rule

    rule = {
        "op": "AND",
        "children": [
            {"probe": "process"},
            {"op": "OR", "children": [{"probe": "primary"}, {"probe": "backup"}]},
        ],
    }

    assert evaluate_rule(rule, {"process": True, "primary": False, "backup": True}) is True
    assert evaluate_rule(rule, {"process": False, "primary": True, "backup": True}) is False


def test_probe_secret_is_only_retained_for_same_auth_type(client, admin_headers):
    host = create_host(client, admin_headers)
    group = create_group(client, admin_headers)
    service = client.post(
        "/api/services",
        headers=admin_headers,
        json={
            "host_id": host["id"],
            "resource_group_id": group["id"],
            "name": "authenticated-service",
            "probes": [
                {
                    "key": "http-main",
                    "name": "主地址",
                    "probe_type": "get",
                    "url": "http://127.0.0.1:9999/health",
                    "auth_type": "bearer",
                    "auth_secret": "original-token",
                    "enabled": True,
                }
            ],
            "health_rule": {"probe": "http-main"},
            "check_interval": 60,
        },
    ).json()

    retained = client.put(
        f"/api/services/{service['id']}",
        headers=admin_headers,
        json={"probes": [{**service["probes"][0], "auth_secret": None}]},
    )
    assert retained.status_code == 200, retained.text

    changed_type = client.put(
        f"/api/services/{service['id']}",
        headers=admin_headers,
        json={
            "probes": [
                {
                    **service["probes"][0],
                    "auth_type": "basic",
                    "auth_username": "ops",
                    "auth_secret": None,
                }
            ]
        },
    )
    assert changed_type.status_code == 422
    assert "Basic 认证缺少用户名或密钥" in changed_type.json()["detail"]


def test_admin_cannot_remove_own_admin_role(client, admin_headers):
    current = client.get("/api/auth/me", headers=admin_headers).json()

    response = client.put(
        f"/api/users/{current['id']}",
        headers=admin_headers,
        json={"is_admin": False},
    )

    assert response.status_code == 400
