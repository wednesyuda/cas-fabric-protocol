"""Transport boundary regressions; no running NATS server is required."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from fabric_nats import NATSFabric
from node_core import Fabric
from nats.errors import NoRespondersError, TimeoutError as NATSTimeoutError


class FakeSubscription:
    def __init__(self, callback):
        self.callback = callback
        self.active = True

    async def unsubscribe(self):
        self.active = False

    async def deliver(self, data, reply=""):
        if self.active:
            await self.callback(SimpleNamespace(data=data, reply=reply))


class FakeClient:
    def __init__(self):
        self.subscriptions = []
        self.request = AsyncMock()

    async def subscribe(self, topic, cb):
        subscription = FakeSubscription(cb)
        self.subscriptions.append(subscription)
        return subscription


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = FakeClient()
        self.fabric = NATSFabric()
        self.fabric._nc = self.client

    async def test_default_connection_uses_environment_url(self):
        with patch.dict(os.environ, {"CAS_NATS_URL": "nats://example.invalid:4333"}), \
                patch("fabric_nats.nats.connect", AsyncMock(return_value=self.client)) as connect:
            await NATSFabric().connect()
        self.assertEqual(connect.call_args.kwargs["servers"], "nats://example.invalid:4333")

    async def test_credentials_in_url_rejected_without_secret_logging(self):
        with patch("fabric_nats.nats.connect", AsyncMock()) as connect:
            with self.assertRaisesRegex(ValueError, "must not contain credentials"):
                await NATSFabric("nats://user:secret@localhost:4222").connect()
            connect.assert_not_called()

    async def test_auth_file_passes_credentials_without_logging_them(self):
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"auth.json"
            path.write_text(json.dumps({"user":"test-role","password":"private-test-secret"}))
            with patch.dict(os.environ,{"CAS_NATS_AUTH_FILE":str(path)}), \
                    patch("fabric_nats.nats.connect",AsyncMock(return_value=self.client)) as connect, \
                    self.assertLogs("cas_fabric.nats",level="INFO") as logs:
                await NATSFabric().connect()
            self.assertEqual(connect.call_args.kwargs["user"],"test-role")
            self.assertNotIn("private-test-secret"," ".join(logs.output))

    async def test_explicit_servers_override_environment(self):
        for servers in ("nats://explicit.invalid:4222", ["nats://one.invalid:4222", "nats://two.invalid:4222"]):
            with self.subTest(servers=servers), \
                    patch.dict(os.environ, {"CAS_NATS_URL": "nats://environment.invalid:4222"}), \
                    patch("fabric_nats.nats.connect", AsyncMock(return_value=self.client)) as connect:
                await NATSFabric(servers=servers).connect()
                self.assertEqual(connect.call_args.kwargs["servers"], servers)

    async def test_no_responders_matches_in_memory_none_contract(self):
        expected = await Fabric().request("missing", {}, timeout=0.001)
        self.assertIsNone(expected)
        self.client.request.side_effect = NoRespondersError()
        self.assertIs(await self.fabric.request("missing", {}), expected)

    async def test_timeout_returns_none(self):
        self.client.request.side_effect = NATSTimeoutError()
        self.assertIsNone(await self.fabric.request("missing", {}))

    async def test_malformed_messages_are_dropped_and_valid_delivery_recovers(self):
        received = []
        await self.fabric.subscribe_async("health", lambda envelope: received.append(envelope["payload"]))
        subscription = self.client.subscriptions[-1]
        for malformed in (b"\xff", b"{", b"[]", b"null", b"42", b'"text"'):
            with self.subTest(data=malformed):
                received.clear()
                await subscription.deliver(malformed)
                await subscription.deliver(b'{"healthy": true}')
                self.assertEqual(received, [{"healthy": True}])

    async def test_subscription_handle_can_stop_delivery(self):
        received = []
        subscription = await self.fabric.subscribe_async("health", received.append)
        self.assertIsNotNone(subscription, "Owners need a subscription handle for cleanup")
        await self.client.subscriptions[-1].deliver(b'{"healthy": true}')
        await subscription.unsubscribe()
        await self.client.subscriptions[-1].deliver(b'{"healthy": false}')
        self.assertEqual(received, [{"payload": {"healthy": True}}])


if __name__ == "__main__":
    unittest.main()
