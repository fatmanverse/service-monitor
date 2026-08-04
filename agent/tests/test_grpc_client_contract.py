import unittest
from unittest.mock import Mock, patch

from service_monitor_agent.client import AgentClient


class GrpcClientContractTests(unittest.TestCase):
    @patch("service_monitor_agent.client.Path.read_bytes", return_value=b"ca")
    @patch("service_monitor_agent.client.grpc.secure_channel")
    def test_client_uses_secure_channel_and_agent_metadata(
        self, secure_channel, _read_bytes
    ):
        channel = Mock()
        secure_channel.return_value = channel
        channel.unary_unary.return_value = Mock(
            return_value=type(
                "Reply",
                (),
                {
                    "protocol_version": 1,
                    "agent_uuid": "agent-uuid-123456",
                    "status": "pending",
                },
            )()
        )

        client = AgentClient("grpcs://monitor.example:50051", ca_file="/etc/ca.pem")
        client.enroll(
            {
                "protocol_version": 1,
                "agent_uuid": "agent-uuid-123456",
                "claim_token": "c" * 32,
                "hostname": "node",
                "runtime_user": "root",
                "os_release": "linux",
                "architecture": "x86_64",
                "glibc_version": "2.35",
                "agent_version": "0.1.0",
            }
        )

        secure_channel.assert_called_once()
        channel.unary_unary.assert_called()
        call = channel.unary_unary.return_value.call_args
        self.assertEqual(call.kwargs["metadata"], ())

    @patch("service_monitor_agent.client.grpc.secure_channel")
    def test_authenticated_rpc_sends_agent_metadata(self, secure_channel):
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
        metadata = rpc.call_args.kwargs["metadata"]
        self.assertIn(("x-agent-id", "agent-id"), metadata)
        self.assertIn(("authorization", "Bearer secret"), metadata)
