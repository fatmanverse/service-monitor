import os

import pytest
import grpc
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"

from app.config import Settings
from app.main import create_app
from app.agent_grpc_service import AgentControlService
from app.protocol_gen import agent_pb2


class GrpcTestContext:
    def __init__(self, metadata=()):
        self._metadata = metadata
        self.code = grpc.StatusCode.OK
        self.details = ""

    def invocation_metadata(self):
        return self._metadata

    def peer(self):
        return "ipv4:127.0.0.1:40000"

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details = details

    def abort(self, code, details):
        self.code = code
        self.details = details
        raise grpc.RpcError(details)


class AgentRpcClient:
    def __init__(self, app):
        self.service = AgentControlService(
            app.state.database,
            app.state.settings,
            app.state.cipher,
            app.state.monitoring,
        )

    def enroll(self, payload):
        return self._invoke(self.service.Enroll, agent_pb2.EnrollRequest(**payload))

    def claim(self, payload):
        return self._invoke(self.service.Claim, agent_pb2.ClaimRequest(**payload))

    def heartbeat(self, payload, metadata):
        return self._invoke(
            self.service.Heartbeat,
            agent_pb2.HeartbeatRequest(**payload),
            metadata,
        )

    def config(self, metadata):
        return self._invoke(
            self.service.GetConfig,
            agent_pb2.ConfigRequest(protocol_version=1),
            metadata,
        )

    def report(self, payload, metadata):
        reports = []
        for values in payload["reports"]:
            report = dict(values)
            report["probes"] = [agent_pb2.ProbeReport(**probe) for probe in report["probes"]]
            reports.append(agent_pb2.ServiceReport(**report))
        return self._invoke(
            self.service.Report,
            agent_pb2.ReportRequest(protocol_version=1, reports=reports),
            metadata,
        )

    @staticmethod
    def _invoke(method, request, metadata=()):
        context = GrpcTestContext(metadata)
        response = method(request, context)
        return response, context


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        app_secret="test-secret-for-service-monitor",
        initial_admin_username="admin",
        initial_admin_password="admin123",
        scheduler_enabled=False,
        testing=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def agent_rpc(client):
    return AgentRpcClient(client.app)
