from concurrent import futures
from datetime import datetime, timedelta
from ipaddress import ip_address

import grpc
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.agent_grpc_service import AgentControlService
from app.protocol_gen import agent_pb2, agent_pb2_grpc
from app.security import SecretCipher
from app.tls_certificates import ensure_instance_tls


def tls_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return (
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ),
        certificate.public_bytes(serialization.Encoding.PEM),
    )


def test_tls_grpc_enrollment_round_trip(client):
    private_key, certificate = tls_material()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    agent_pb2_grpc.add_AgentControlServicer_to_server(
        AgentControlService(
            client.app.state.database,
            client.app.state.settings,
            SecretCipher(client.app.state.settings.app_secret),
            client.app.state.monitoring,
        ),
        server,
    )
    credentials = grpc.ssl_server_credentials(((private_key, certificate),))
    port = server.add_secure_port("127.0.0.1:0", credentials)
    server.start()
    try:
        channel = grpc.secure_channel(
            f"localhost:{port}",
            grpc.ssl_channel_credentials(root_certificates=certificate),
        )
        stub = agent_pb2_grpc.AgentControlStub(channel)
        response = stub.Enroll(
            agent_pb2.EnrollRequest(
                protocol_version=1,
                agent_uuid="integration-agent-uuid",
                claim_token="integration-claim-token-that-is-long-enough",
                hostname="integration-node",
                runtime_user="root",
                os_release="Linux",
                architecture="x86_64",
                glibc_version="2.28",
                agent_version="0.1.0",
            ),
            timeout=5,
        )
        assert response.agent_uuid == "integration-agent-uuid"
        assert response.status == "pending"
    finally:
        server.stop(grace=0).wait()


def test_generated_instance_ca_supports_strict_server_identity(client, tmp_path):
    tls_files = ensure_instance_tls(tmp_path / "certs")
    assert ensure_instance_tls(tmp_path / "certs") == tls_files
    for path in [
        tls_files.certificate,
        tls_files.private_key,
        tls_files.ca_certificate,
        tmp_path / "certs" / "ca.key",
    ]:
        assert path.stat().st_mode & 0o777 == 0o600

    server_certificate = x509.load_pem_x509_certificate(
        tls_files.certificate.read_bytes()
    )
    ca_certificate = x509.load_pem_x509_certificate(
        tls_files.ca_certificate.read_bytes()
    )
    assert server_certificate.issuer == ca_certificate.subject
    assert "service-monitor-server" in server_certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value.get_values_for_type(x509.DNSName)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    agent_pb2_grpc.add_AgentControlServicer_to_server(
        AgentControlService(
            client.app.state.database,
            client.app.state.settings,
            SecretCipher(client.app.state.settings.app_secret),
            client.app.state.monitoring,
        ),
        server,
    )
    credentials = grpc.ssl_server_credentials(
        ((tls_files.private_key.read_bytes(), tls_files.certificate.read_bytes()),)
    )
    port = server.add_secure_port("127.0.0.1:0", credentials)
    server.start()
    try:
        channel = grpc.secure_channel(
            f"127.0.0.1:{port}",
            grpc.ssl_channel_credentials(
                root_certificates=tls_files.ca_certificate.read_bytes()
            ),
            options=(("grpc.ssl_target_name_override", "service-monitor-server"),),
        )
        response = agent_pb2_grpc.AgentControlStub(channel).Enroll(
            agent_pb2.EnrollRequest(
                protocol_version=1,
                agent_uuid="generated-ca-agent-uuid",
                claim_token="generated-ca-claim-token-that-is-long-enough",
                hostname="generated-ca-node",
                runtime_user="root",
                os_release="Linux",
                architecture="x86_64",
                glibc_version="2.28",
                agent_version="0.1.0",
            ),
            timeout=5,
        )
        assert response.status == "pending"
    finally:
        server.stop(grace=0).wait()
