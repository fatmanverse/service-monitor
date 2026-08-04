from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass(frozen=True)
class AgentConfig:
    center_url: str
    ca_file: Optional[str]
    heartbeat_interval: int
    state_path: str


def load_config(path: str) -> AgentConfig:
    with Path(path).open("rb") as handle:
        values = tomllib.load(handle)
    center_url = values.get("center_url", "").rstrip("/")
    if not center_url.startswith(("grpcs://", "https://")):
        raise ValueError("center_url 必须使用 TLS gRPC 地址")
    interval = int(values.get("heartbeat_interval", 30))
    if interval < 10:
        raise ValueError("heartbeat_interval 不能低于 10 秒")
    return AgentConfig(
        center_url=center_url,
        ca_file=values.get("ca_file") or None,
        heartbeat_interval=interval,
        state_path=values.get("state_path", "/var/lib/service-monitor-agent/agent.db"),
    )
