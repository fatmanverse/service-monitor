import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


DEFAULT_TLS_SERVER_NAME = "service-monitor-server"


@dataclass(frozen=True)
class AgentTlsFiles:
    certificate: Path
    private_key: Path
    ca_certificate: Optional[Path]


def resolve_agent_tls_files(settings) -> AgentTlsFiles:
    certificate = _optional_path(settings.agent_grpc_cert_file)
    private_key = _optional_path(settings.agent_grpc_key_file)
    ca_certificate = _optional_path(settings.agent_grpc_ca_file)
    if certificate or private_key:
        if not certificate or not private_key:
            raise ValueError(
                "gRPC TLS 必须同时配置 AGENT_GRPC_CERT_FILE 和 AGENT_GRPC_KEY_FILE"
            )
        _require_file(certificate, "gRPC TLS 服务端证书")
        _require_file(private_key, "gRPC TLS 服务端私钥")
        if ca_certificate:
            _require_file(ca_certificate, "Agent 公共 CA 证书")
        return AgentTlsFiles(certificate, private_key, ca_certificate)
    if ca_certificate:
        raise ValueError(
            "AGENT_GRPC_CA_FILE 不能在缺少服务端证书和私钥时单独配置"
        )
    return ensure_instance_tls(
        Path(settings.agent_grpc_cert_dir), settings.agent_grpc_tls_server_name
    )


def ensure_instance_tls(
    directory: Path,
    server_name: str = DEFAULT_TLS_SERVER_NAME,
) -> AgentTlsFiles:
    directory = directory.resolve()
    files = AgentTlsFiles(
        certificate=directory / "server.crt",
        private_key=directory / "server.key",
        ca_certificate=directory / "ca.crt",
    )
    ca_key_path = directory / "ca.key"
    paths = [files.certificate, files.private_key, files.ca_certificate, ca_key_path]
    existing = [path.exists() for path in paths]
    if all(existing):
        return files
    if any(existing):
        raise ValueError(
            f"TLS 证书目录不完整，请修复或清空后重试: {directory}"
        )

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    now = datetime.utcnow()
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Service Monitor Instance CA")]
    )
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, server_name)])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(server_name)]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )

    _write_private_key(ca_key_path, ca_key)
    _write_certificate(files.ca_certificate, ca_cert)
    _write_private_key(files.private_key, server_key)
    _write_certificate(files.certificate, server_cert)
    return files


def _optional_path(value: str) -> Optional[Path]:
    return Path(value).expanduser().resolve() if value else None


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label}不存在: {path}")


def _write_private_key(path: Path, key) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(path, 0o600)


def _write_certificate(path: Path, certificate: x509.Certificate) -> None:
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    os.chmod(path, 0o600)
