from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class LoginInput(BaseModel):
    username: str
    password: str


class PasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        if self.new_password == self.current_password:
            raise ValueError("新密码不能与当前密码相同")
        return self


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class CurrentUserOutput(UserSummary):
    pass


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    is_admin: bool = False
    is_active: bool = True


class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class ResourceGroupGrantInput(BaseModel):
    resource_group_ids: List[int]


class ServiceGrantInput(BaseModel):
    service_ids: List[int]


class ResourceGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class ResourceGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class ResourceGroupOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    service_count: int = 0
    user_count: int = 0
    created_at: datetime


class AlertConfigReference(BaseModel):
    id: int
    name: str
    enabled: bool


class HostBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    hostname: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    auth_type: Literal["password", "key"] = "password"
    password: Optional[str] = None
    private_key_path: Optional[str] = Field(default=None, max_length=500)
    check_interval: int = Field(default=60, ge=60, le=86400)
    enabled: bool = True
    alert_config_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_auth(self):
        if self.auth_type == "password" and not self.password:
            raise ValueError("password authentication requires password")
        if self.auth_type == "key" and not self.private_key_path:
            raise ValueError("key authentication requires private_key_path")
        return self


class HostCreate(HostBase):
    pass


class HostUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, min_length=1, max_length=100)
    auth_type: Optional[Literal["password", "key"]] = None
    password: Optional[str] = None
    private_key_path: Optional[str] = Field(default=None, max_length=500)
    check_interval: Optional[int] = Field(default=None, ge=60, le=86400)
    enabled: Optional[bool] = None
    alert_config_ids: Optional[List[int]] = None


class HostOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hostname: str
    port: Optional[int]
    username: str
    auth_type: str
    execution_mode: str
    private_key_path: Optional[str]
    check_interval: int
    enabled: bool
    alert_configs: List[AlertConfigReference] = Field(default_factory=list)
    status: str
    last_checked_at: Optional[datetime]
    last_error: Optional[str]
    next_check_at: datetime
    created_at: datetime


class ServiceProbeInput(BaseModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    probe_type: Literal["process", "get", "post"]
    process_pattern: Optional[str] = Field(default=None, max_length=500)
    url: Optional[HttpUrl] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[dict] = None
    auth_type: Literal["none", "basic", "bearer"] = "none"
    auth_username: Optional[str] = None
    auth_secret: Optional[str] = None
    expected_status: int = Field(default=200, ge=100, le=599)
    timeout_seconds: int = Field(default=10, ge=1, le=120)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_probe(self):
        if self.probe_type == "process" and not self.process_pattern:
            raise ValueError("process probe requires process_pattern")
        if self.probe_type in {"get", "post"} and not self.url:
            raise ValueError("HTTP probe requires url")
        return self


class ServiceProbeOutput(BaseModel):
    id: int
    key: str
    name: str
    probe_type: str
    process_pattern: Optional[str]
    url: Optional[str]
    headers: Dict[str, str]
    body: Optional[dict]
    auth_type: str
    auth_username: Optional[str]
    expected_status: int
    timeout_seconds: int
    enabled: bool
    last_success: Optional[bool]
    last_checked_at: Optional[datetime]
    last_error: Optional[str]
    last_response_ms: Optional[int]


class ServiceBase(BaseModel):
    host_id: int
    # Optional: an unbound service is visible to admins and to users holding a
    # direct grant in `user_services`.
    resource_group_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=100)
    probes: List[ServiceProbeInput] = Field(min_length=1, max_length=50)
    health_rule: dict
    start_command: Optional[str] = None
    start_user: Optional[str] = Field(default=None, max_length=100)
    check_interval: int = Field(default=60, ge=60, le=86400)
    enabled: bool = False
    auto_restart: bool = False
    alert_config_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_service(self):
        keys = [probe.key for probe in self.probes]
        if len(keys) != len(set(keys)):
            raise ValueError("probe keys must be unique")
        if not any(probe.enabled for probe in self.probes):
            raise ValueError("at least one probe must be enabled")
        if self.auto_restart and not self.start_command:
            raise ValueError("auto restart requires start_command")
        return self


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    host_id: Optional[int] = None
    resource_group_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    probes: Optional[List[ServiceProbeInput]] = Field(default=None, min_length=1, max_length=50)
    health_rule: Optional[dict] = None
    start_command: Optional[str] = None
    start_user: Optional[str] = Field(default=None, max_length=100)
    check_interval: Optional[int] = Field(default=None, ge=60, le=86400)
    enabled: Optional[bool] = None
    auto_restart: Optional[bool] = None
    alert_config_ids: Optional[List[int]] = None


class ServiceOutput(BaseModel):
    id: int
    host_id: int
    host_name: str
    resource_group_id: Optional[int]
    resource_group_name: Optional[str]
    name: str
    probes: List[ServiceProbeOutput]
    health_rule: dict
    start_command: Optional[str]
    start_user: Optional[str]
    check_interval: int
    enabled: bool
    auto_restart: bool
    alert_configs: List[AlertConfigReference]
    status: str
    last_checked_at: Optional[datetime]
    last_error: Optional[str]
    last_response_ms: Optional[int]
    next_check_at: datetime
    created_at: datetime


class ProbeResultOutput(BaseModel):
    mode: Literal["immediate", "queued"] = "immediate"
    success: Optional[bool]
    status: str
    message: str
    response_ms: Optional[int] = None
    restarted: bool = False
    command_id: Optional[str] = None
    command_status: Optional[str] = None
    probes: List["ProbeItemResultOutput"] = Field(default_factory=list)


class ProbeItemResultOutput(BaseModel):
    key: str
    name: str
    success: bool
    message: str
    response_ms: Optional[int] = None


class ProbeLogOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    success: bool
    message: str
    response_ms: Optional[int]
    checked_at: datetime


class ProbeLogPageOutput(BaseModel):
    items: List[ProbeLogOutput]
    next_cursor: Optional[str] = None


class AlertConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enabled: bool
    webhook_url: HttpUrl


class AlertConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    enabled: Optional[bool] = None
    webhook_url: Optional[HttpUrl] = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in {"name", "enabled"} & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AlertConfigOutput(BaseModel):
    id: int
    name: str
    enabled: bool
    webhook_configured: bool
    service_count: int
    host_count: int
    created_at: datetime
    updated_at: datetime


class MessageOutput(BaseModel):
    message: str
