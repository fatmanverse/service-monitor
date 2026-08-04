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
