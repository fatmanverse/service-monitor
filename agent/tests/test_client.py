import unittest
from unittest.mock import Mock, patch

import grpc

from service_monitor_agent.client import (
    AgentAuthenticationError,
    AgentClient,
)


class RpcFailure(grpc.RpcError):
    def __init__(self, code, detail):
        self._code = code
        self._detail = detail

    def code(self):
        return self._code

    def details(self):
        return self._detail


class ClientTests(unittest.TestCase):
    @patch("service_monitor_agent.client.Path.read_bytes", return_value=b"ca")
    @patch("service_monitor_agent.client.grpc.ssl_channel_credentials")
    @patch("service_monitor_agent.client.grpc.secure_channel")
    def test_custom_ca_builds_strict_tls_credentials(
        self, secure_channel, ssl_channel_credentials, _read_bytes
    ):
        channel = Mock()
        secure_channel.return_value = channel
        AgentClient("grpcs://monitor.example:50051", "/etc/ca.pem")
        ssl_channel_credentials.assert_called_once_with(root_certificates=b"ca")
        secure_channel.assert_called_once_with(
            "monitor.example:50051", ssl_channel_credentials.return_value
        )

    @patch("service_monitor_agent.client.grpc.secure_channel")
    def test_authenticated_rpc_sets_agent_metadata(self, secure_channel):
        channel = Mock()
        secure_channel.return_value = channel
        rpc = Mock(return_value=type("Reply", (), {
            "protocol_version": 1,
            "config_revision": 1,
            "config_changed": False,
            "commands": [],
        })())
        channel.unary_unary.return_value = rpc
        client = AgentClient("monitor.example:50051")
        client.heartbeat("agent-id", "secret", 0, 0)
        self.assertIn(("x-agent-id", "agent-id"), rpc.call_args.kwargs["metadata"])
        self.assertIn(
            ("authorization", "Bearer secret"), rpc.call_args.kwargs["metadata"]
        )

    @patch("service_monitor_agent.client.grpc.secure_channel")
    def test_unauthenticated_rpc_is_fatal_authentication_error(self, secure_channel):
        channel = Mock()
        secure_channel.return_value = channel
        channel.unary_unary.return_value = Mock(
            side_effect=RpcFailure(grpc.StatusCode.UNAUTHENTICATED, "revoked")
        )
        client = AgentClient("monitor.example:50051")
        with self.assertRaisesRegex(AgentAuthenticationError, "revoked"):
            client.heartbeat("agent-id", "old-secret", 0, 0)


if __name__ == "__main__":
    unittest.main()
