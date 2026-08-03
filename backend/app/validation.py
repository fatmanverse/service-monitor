from typing import Optional

from fastapi import HTTPException


def validate_host_auth(
    auth_type: str,
    password_encrypted: Optional[str],
    private_key_path: Optional[str],
) -> None:
    if auth_type == "password" and not password_encrypted:
        raise HTTPException(status_code=422, detail="密码认证必须提供 SSH 密码")
    if auth_type == "key" and not private_key_path:
        raise HTTPException(status_code=422, detail="私钥认证必须提供服务器本地私钥路径")


def validate_service_configuration(
    probe_type: str,
    process_pattern: Optional[str],
    url: Optional[str],
    auth_type: str,
    auth_username: Optional[str],
    auth_secret_encrypted: Optional[str],
    auto_restart: bool,
    start_command: Optional[str],
) -> None:
    if probe_type == "process" and not process_pattern:
        raise HTTPException(status_code=422, detail="进程探活必须提供进程匹配内容")
    if probe_type in {"get", "post"} and not url:
        raise HTTPException(status_code=422, detail="HTTP 探活必须提供 URL")
    if auth_type == "basic" and (not auth_username or not auth_secret_encrypted):
        raise HTTPException(status_code=422, detail="Basic 认证必须提供用户名和密钥")
    if auth_type == "bearer" and not auth_secret_encrypted:
        raise HTTPException(status_code=422, detail="Bearer 认证必须提供密钥")
    if auto_restart and not start_command:
        raise HTTPException(status_code=422, detail="自动拉起必须提供服务启动命令")

