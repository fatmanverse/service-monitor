from concurrent import futures
import grpc

from .agent_grpc_service import AgentControlService
from .protocol_gen import agent_pb2_grpc
from .tls_certificates import resolve_agent_tls_files


def create_grpc_server(database, settings, cipher, monitor):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    agent_pb2_grpc.add_AgentControlServicer_to_server(
        AgentControlService(database, settings, cipher, monitor), server
    )
    tls_files = resolve_agent_tls_files(settings)
    cert_chain = tls_files.certificate.read_bytes()
    private_key = tls_files.private_key.read_bytes()
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
