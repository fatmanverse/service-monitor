from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class UserService(Base):
    __tablename__ = "user_services"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)


class UserResourceGroup(Base):
    __tablename__ = "user_resource_groups"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    resource_group_id: Mapped[int] = mapped_column(
        ForeignKey("resource_groups.id", ondelete="CASCADE"), primary_key=True
    )


class ServiceAlertConfig(Base):
    __tablename__ = "service_alert_configs"

    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)
    alert_config_id: Mapped[int] = mapped_column(
        ForeignKey("alert_configs.id", ondelete="CASCADE"), primary_key=True
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    services: Mapped[List["Service"]] = relationship(secondary="user_services", back_populates="users")
    resource_groups: Mapped[List["ResourceGroup"]] = relationship(
        secondary="user_resource_groups", back_populates="users"
    )


class ResourceGroup(Base):
    __tablename__ = "resource_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    services: Mapped[List["Service"]] = relationship(back_populates="resource_group")
    users: Mapped[List[User]] = relationship(
        secondary="user_resource_groups", back_populates="resource_groups"
    )


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(100))
    auth_type: Mapped[str] = mapped_column(String(16), default="password")
    password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    private_key_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    services: Mapped[List["Service"]] = relationship(
        back_populates="host", cascade="all, delete-orphan", passive_deletes=True
    )


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("host_id", "name", name="uq_service_host_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"), index=True)
    resource_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resource_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    health_rule_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    probe_type: Mapped[str] = mapped_column(String(16))
    process_pattern: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    headers_json: Mapped[str] = mapped_column(Text, default="{}")
    body_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(16), default="none")
    auth_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    start_command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_restart: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_response_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    host: Mapped[Host] = relationship(back_populates="services")
    resource_group: Mapped[Optional[ResourceGroup]] = relationship(back_populates="services")
    users: Mapped[List[User]] = relationship(secondary="user_services", back_populates="services")
    probes: Mapped[List["ServiceProbe"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ServiceProbe.id",
    )
    logs: Mapped[List["ProbeLog"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    alert_configs: Mapped[List["AlertConfig"]] = relationship(
        secondary="service_alert_configs", back_populates="services", passive_deletes=True
    )


class ServiceProbe(Base):
    __tablename__ = "service_probes"
    __table_args__ = (UniqueConstraint("service_id", "key", name="uq_service_probe_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    probe_type: Mapped[str] = mapped_column(String(16))
    process_pattern: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    headers_json: Mapped[str] = mapped_column(Text, default="{}")
    body_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(16), default="none")
    auth_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_response_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    service: Mapped[Service] = relationship(back_populates="probes")


class ProbeLog(Base):
    __tablename__ = "probe_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[str] = mapped_column(Text)
    response_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    services: Mapped[List[Service]] = relationship(
        secondary="service_alert_configs", back_populates="alert_configs", passive_deletes=True
    )


class AppMigration(Base):
    __tablename__ = "app_migrations"

    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
