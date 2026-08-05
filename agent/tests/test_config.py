from service_monitor_agent.config import load_config


def test_load_config_supports_instance_ca_and_fixed_server_identity(tmp_path):
    config_path = tmp_path / "agent.toml"
    config_path.write_text(
        'center_url = "grpcs://10.0.0.10:50051"\n'
        'ca_file = "/etc/service-monitor-agent/ca.crt"\n'
        'tls_server_name = "service-monitor-server"\n'
        'heartbeat_interval = 30\n'
        'state_path = "/var/lib/service-monitor-agent/agent.db"\n'
    )

    config = load_config(str(config_path))

    assert config.ca_file == "/etc/service-monitor-agent/ca.crt"
    assert config.tls_server_name == "service-monitor-server"
