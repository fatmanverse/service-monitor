from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .schemas import HostOutput


class AgentEnrollInput(BaseModel):
    protocol_version: Literal[1]
    agent_uuid: str = Field(min_length=16, max_length=64)
    claim_token: str = Field(min_length=32, max_length=256)
    hostname: str = Field(min_length=1, max_length=255)
    runtime_user: str = Field(min_length=1, max_length=100)
    os_release: str = Field(min_length=1, max_length=500)
    architecture: Literal["x86_64", "arm64", "aarch64"]
    glibc_version: str = Field(min_length=1, max_length=32)
    agent_version: str = Field(min_length=1, max_length=32)


class AgentEnrollOutput(BaseModel):
    protocol_version: Literal[1] = 1
    agent_uuid: str
    status: str


class AgentClaimInput(BaseModel):
    protocol_version: Literal[1]
    agent_uuid: str = Field(min_length=16, max_length=64)
    claim_token: str = Field(min_length=32, max_length=256)


class AgentClaimOutput(BaseModel):
    protocol_version: Literal[1] = 1
    agent_uuid: str
    agent_secret: str


class AgentApproveInput(BaseModel):
    mode: Literal["new", "bind"]
    host_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    host_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.mode == "new" and not self.host_name:
            raise ValueError("新建主机必须提供主机名称")
        if self.mode == "bind" and not self.host_id:
            raise ValueError("绑定主机必须提供 host_id")
        return self


class AgentHeartbeatInput(BaseModel):
    protocol_version: Literal[1]
    config_revision: int = Field(ge=0)
    outbox_size: int = Field(ge=0)


class AgentCommandContract(BaseModel):
    command_id: str
    service_id: int
    command_type: Literal["probe_service", "restart_service"]
    status: Literal["claimed"]
    expires_at: datetime


class AgentCommandStatusOutput(BaseModel):
    command_id: str
    service_id: int
    command_type: str
    status: str
    result: Optional[dict]
    created_at: datetime
    claimed_at: Optional[datetime]
    finished_at: Optional[datetime]
    expires_at: datetime


class AgentHeartbeatOutput(BaseModel):
    protocol_version: Literal[1] = 1
    status: Literal["ok"] = "ok"
    config_revision: int
    config_changed: bool
    commands: List[AgentCommandContract] = Field(default_factory=list)


class AgentProbeConfig(BaseModel):
    key: str
    name: str
    probe_type: Literal["process", "get", "post"]
    process_pattern: Optional[str]
    url: Optional[str]
    headers: Dict[str, str]
    body: Optional[dict]
    auth_type: Literal["none", "basic", "bearer"]
    auth_username: Optional[str]
    auth_secret: Optional[str]
    expected_status: int
    timeout_seconds: int


class AgentServiceConfig(BaseModel):
    id: int
    name: str
    probes: List[AgentProbeConfig]
    health_rule: dict
    start_command: Optional[str]
    start_user: Optional[str]
    check_interval: int
    auto_restart: bool


class AgentConfigOutput(BaseModel):
    protocol_version: Literal[1] = 1
    config_revision: int
    host_id: int
    services: List[AgentServiceConfig]


class AgentProbeReport(BaseModel):
    key: str
    success: bool
    message: str
    response_ms: Optional[int] = None


class AgentServiceReport(BaseModel):
    report_id: str = Field(min_length=1, max_length=64)
    report_sequence: int = Field(ge=1)
    service_id: int
    success: bool
    message: str
    response_ms: Optional[int] = None
    restarted: bool = False
    occurred_at: datetime
    probes: List[AgentProbeReport]
    command_id: Optional[str] = Field(default=None, max_length=64)


class AgentReportsInput(BaseModel):
    protocol_version: Literal[1]
    reports: List[AgentServiceReport] = Field(min_length=1, max_length=500)


class AgentReportsOutput(BaseModel):
    protocol_version: Literal[1] = 1
    accepted: int
    duplicates: int


class AgentOutput(BaseModel):
    id: int
    agent_uuid: str
    status: str
    hostname: str
    runtime_user: str
    os_release: str
    architecture: str
    glibc_version: str
    agent_version: str
    last_seen_at: Optional[datetime]
    last_ip: Optional[str]
    config_revision: int
    created_at: datetime
    approved_at: Optional[datetime]
    revoked_at: Optional[datetime]
    host: Optional[HostOutput]
    ssh_credentials_removed: bool = False


class AgentSecretRotationOutput(BaseModel):
    agent: AgentOutput
    agent_secret: str
