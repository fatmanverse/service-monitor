def create_host(client, headers, name="node-a", alert_config_ids=None):
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
            "alert_config_ids": alert_config_ids or [],
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


def test_host_can_select_multiple_alert_configs(client, admin_headers):
    first = create_alert(client, admin_headers, "节点值班群")
    second = create_alert(client, admin_headers, "基础设施群")
    host = create_host(
        client,
        admin_headers,
        alert_config_ids=[first["id"], second["id"]],
    )

    assert {item["id"] for item in host["alert_configs"]} == {first["id"], second["id"]}
    counts = {item["id"]: item["host_count"] for item in client.get("/api/alerts", headers=admin_headers).json()}
    assert counts[first["id"]] == 1
    assert counts[second["id"]] == 1

    deleted = client.delete(f"/api/alerts/{first['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    unchanged = client.get("/api/hosts", headers=admin_headers).json()[0]
    assert [item["id"] for item in unchanged["alert_configs"]] == [second["id"]]

    updated = client.put(
        f"/api/hosts/{host['id']}",
        headers=admin_headers,
        json={"alert_config_ids": []},
    )
    assert updated.status_code == 200
    assert updated.json()["alert_configs"] == []


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


def test_host_alerts_on_offline_transition_and_recovery(client, admin_headers, monkeypatch):
    from app.models import Host
    from app.monitoring import ProbeResult

    alert = create_alert(client, admin_headers, "节点告警群")
    host_data = create_host(client, admin_headers, alert_config_ids=[alert["id"]])
    initially_online_host = create_host(
        client,
        admin_headers,
        name="node-b",
        alert_config_ids=[alert["id"]],
    )
    monitor = client.app.state.monitoring
    deliveries = []

    class FakeClient:
        def close(self):
            pass

    outcomes = iter([
        RuntimeError("SSH 不可达"),
        RuntimeError("SSH 仍不可达"),
        FakeClient(),
        FakeClient(),
    ])

    def fake_connect(_host):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def fake_alert(configs, host, previous_status, result):
        deliveries.append((len(configs), host.id, previous_status, result.status))
        return ProbeResult(True, "发送成功")

    monkeypatch.setattr(monitor, "_connect_ssh", fake_connect)
    monkeypatch.setattr(monitor, "_send_host_status_alert", fake_alert)
    with client.app.state.database.session_factory() as db:
        host = db.get(Host, host_data["id"])
        monitor.check_host(db, host)
        monitor.check_host(db, host)
        monitor.check_host(db, host)
        monitor.check_host(db, db.get(Host, initially_online_host["id"]))

    assert deliveries == [
        (1, host_data["id"], "unknown", "offline"),
        (1, host_data["id"], "offline", "online"),
    ]


def test_offline_host_pauses_service_probe_and_alerts(client, admin_headers, monkeypatch):
    from sqlalchemy import func, select

    from app.models import Host, ProbeLog, Service

    alert = create_alert(client, admin_headers, "服务告警群")
    host_data = create_host(client, admin_headers)
    service_data = create_service(
        client,
        admin_headers,
        host_data["id"],
        alert_config_ids=[alert["id"]],
    )
    monitor = client.app.state.monitoring

    def unexpected(*_args, **_kwargs):
        raise AssertionError("节点离线时不应执行服务探活、自动拉起或服务告警")

    monkeypatch.setattr(monitor, "_run_service_probes", unexpected)
    monkeypatch.setattr(monitor, "restart_service", unexpected)
    monkeypatch.setattr(monitor, "_restart_service_locked", unexpected)
    monkeypatch.setattr(monitor, "_send_status_alert", unexpected)
    with client.app.state.database.session_factory() as db:
        host = db.get(Host, host_data["id"])
        host.status = "offline"
        service = db.get(Service, service_data["id"])
        service.status = "online"
        service.auto_restart = True
        service.start_command = "systemctl start api-service"
        previous_checked_at = service.last_checked_at
        db.commit()

        result = monitor.check_service(db, service)
        restart_result = monitor.restart_and_check(db, service)
        log_count = db.scalar(
            select(func.count(ProbeLog.id)).where(ProbeLog.service_id == service.id)
        )

        assert result.success is False
        assert result.message == "节点离线，已暂停服务探活"
        assert restart_result.success is False
        assert restart_result.message == "节点离线，已暂停服务启动与探活"
        assert service.status == "online"
        assert service.last_checked_at == previous_checked_at
        assert log_count == 0


def test_scheduler_checks_due_hosts_before_dispatching_services(client, admin_headers, monkeypatch):
    from app.models import Host

    host_data = create_host(client, admin_headers)
    create_service(client, admin_headers, host_data["id"])
    scheduler = client.app.state.scheduler
    monitor = client.app.state.monitoring
    calls = []

    def check_host(db, host):
        calls.append("host")
        host.status = "offline"
        db.commit()

    def check_service(_db, _service):
        calls.append("service")

    monkeypatch.setattr(monitor, "check_host", check_host)
    monkeypatch.setattr(monitor, "check_service", check_service)
    scheduler.run_due_checks()

    with client.app.state.database.session_factory() as db:
        assert db.get(Host, host_data["id"]).status == "offline"
    assert calls == ["host"]


def test_systemd_probe_command_is_parsed_safely():
    from app.monitoring import MonitoringService

    assert MonitoringService._systemd_unit("systemctl status nginx") == "nginx"
    assert MonitoringService._systemd_unit("systemctl is-active app@worker.service") == "app@worker.service"
    assert MonitoringService._systemd_unit("systemctl status 'bad; reboot'") is None
    assert MonitoringService._systemd_unit("nginx") is None


def test_systemd_probe_uses_active_status_exit_code(monkeypatch):
    from types import SimpleNamespace

    from app.monitoring import MonitoringService

    class FakeStream:
        def __init__(self, value=b"", exit_code=0):
            self.value = value
            self.channel = SimpleNamespace(recv_exit_status=lambda: exit_code)

        def read(self):
            return self.value

    commands = []
    exit_codes = iter([0, 3])

    class FakeClient:
        def exec_command(self, command, timeout):
            commands.append((command, timeout))
            return None, FakeStream(exit_code=next(exit_codes)), FakeStream()

        def close(self):
            pass

    monitor = object.__new__(MonitoringService)
    monkeypatch.setattr(monitor, "_connect_ssh", lambda _host: FakeClient())
    host = SimpleNamespace()
    probe = SimpleNamespace(process_pattern="systemctl status nginx", timeout_seconds=10)

    active = monitor._probe_process(host, probe)
    inactive = monitor._probe_process(host, probe)

    assert commands == [
        ("systemctl is-active --quiet -- nginx", 10),
        ("systemctl is-active --quiet -- nginx", 10),
    ]
    assert active.success is True
    assert active.message == "systemd 服务 nginx 在线"
    assert inactive.success is False
    assert inactive.message == "systemd 服务 nginx 未运行"


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
