from concurrent import futures
from pathlib import Path

import grpc

from .agent_grpc_service import AgentControlService
from .protocol_gen import agent_pb2_grpc


def create_grpc_server(database, settings, cipher, monitor):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    agent_pb2_grpc.add_AgentControlServicer_to_server(
        AgentControlService(database, settings, cipher, monitor), server
    )
    if not settings.agent_grpc_cert_file or not settings.agent_grpc_key_file:
        raise ValueError("gRPC TLS requires AGENT_GRPC_CERT_FILE and AGENT_GRPC_KEY_FILE")
    cert_chain = Path(settings.agent_grpc_cert_file).read_bytes()
    private_key = Path(settings.agent_grpc_key_file).read_bytes()
    credentials = grpc.ssl_server_credentials(((private_key, cert_chain),))
    server.add_secure_port(settings.agent_grpc_bind, credentials)
    return server


def serve(database, settings, cipher, monitor):
    server = create_grpc_server(database, settings, cipher, monitor)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    from .config import get_settings
    from .database import Database
    from .migrations import migrate_database
    from .monitoring import MonitoringService
    from .security import SecretCipher

    settings = get_settings()
    database = Database(settings)
    cipher = SecretCipher(settings.app_secret)
    monitor = MonitoringService(cipher, probe_workers=settings.monitor_workers * 2)
    try:
        migrate_database(database)
        serve(database, settings, cipher, monitor)
    finally:
        monitor.shutdown()
