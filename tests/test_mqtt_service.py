import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pyserialgateway.mqtt_service.adapters import (
    LegacyGatewayMQTTAdapter,
    RefactoredGatewayMQTTAdapter,
)
from pyserialgateway.mqtt_service.config import MQTTConfig
from pyserialgateway.mqtt_service.events import GatewayEvent
from pyserialgateway.mqtt_service.mirroring import MQTTMirroringQueue
from pyserialgateway.mqtt_service.service import MQTTService
from pyserialgateway.mqtt_service.topics import MQTTTopics


class FakeResult:
    rc = 0


class FakeClient:
    def __init__(self):
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.published = []
        self.subscriptions = []
        self.will = None

    def username_pw_set(self, username, password=None):
        self.username = username
        self.password = password

    def tls_set(self, **kwargs):
        self.tls_kwargs = kwargs

    def tls_insecure_set(self, value):
        self.tls_insecure = value

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def connect(self, broker, port, keepalive):
        self.connection = (broker, port, keepalive)
        return 0

    def loop_start(self):
        return None

    def loop_stop(self):
        return None

    def disconnect(self):
        return None

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))
        return FakeResult()


class FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item, *args, **kwargs):
        self.items.append((item, args, kwargs))
        return "http-queue-result"


class MQTTServiceTests(unittest.TestCase):
    def make_service(self, status_interval_seconds=7200):
        temp = tempfile.NamedTemporaryFile(suffix=".mqtt.db", delete=False)
        temp.close()
        log_file = temp.name + ".log"
        self.addCleanup(lambda: os.path.exists(temp.name) and os.unlink(temp.name))
        self.addCleanup(lambda: os.path.exists(log_file) and os.unlink(log_file))
        config = MQTTConfig(
            enabled=True,
            broker="broker.local",
            port=1883,
            username="user",
            password="secret",
            tls=False,
            gateway_id="gw-01",
            topic_root="s3/zigbee",
            buffer_db=temp.name,
            status_interval_seconds=status_interval_seconds,
            log_file=log_file,
        )
        fake = FakeClient()
        return MQTTService(config=config, client=fake), fake

    def test_topics_are_gateway_scoped(self):
        topics = MQTTTopics("s3/zigbee", "gw-01")
        self.assertEqual(topics.status(), "s3/zigbee/gw-01/status")
        self.assertEqual(
            topics.telemetry("001A"),
            "mainserver/node_zigbee/gw-01/snode/heartbeat/001A",
        )
        self.assertEqual(topics.command(), "s3/zigbee/gw-01/cmd")
        self.assertEqual(topics.node_command(), "s3/zigbee/gw-01/node/+/cmd")

    def test_legacy_and_refactored_adapters_emit_same_event(self):
        class RecordingService:
            def __init__(self):
                self.events = []

            def publish_event(self, event):
                self.events.append(event)

        legacy_service = RecordingService()
        ref_service = RecordingService()
        legacy = LegacyGatewayMQTTAdapter(legacy_service, "gw-01")
        refactored = RefactoredGatewayMQTTAdapter(ref_service, "gw-01")

        legacy.publish_validated_packet("001A", "H1|001A|...", "H1")
        refactored.publish_validated_packet("001A", "H1|001A|...", "H1")

        legacy_event = legacy_service.events[0].to_dict()
        ref_event = ref_service.events[0].to_dict()
        legacy_event.pop("timestamp")
        ref_event.pop("timestamp")

        self.assertEqual(legacy_event, ref_event)
        self.assertTrue(legacy_service.events[0].timestamp)
        self.assertTrue(ref_service.events[0].timestamp)

    def test_adapter_decodes_byte_payload_to_utf8(self):
        class RecordingService:
            def __init__(self):
                self.events = []

            def publish_event(self, event):
                self.events.append(event)

        service = RecordingService()
        adapter = RefactoredGatewayMQTTAdapter(service, "gw-01")
        adapter.publish_validated_packet(
            "001A",
            b"#H1|001A|0001|01-00:00:00|synthetic#",
            "H1",
        )

        self.assertEqual(
            service.events[0].payload,
            "#H1|001A|0001|01-00:00:00|synthetic#",
        )
        self.assertIsInstance(service.events[0].payload, str)

    def test_live_telemetry_is_not_buffered_when_disconnected(self):
        service, _ = self.make_service()
        event = GatewayEvent(
            event_type="heartbeat",
            gateway_id="gw-01",
            node_id="001A",
            packet_type="H1",
            payload="H1|001A|...",
        )
        service.publish_event(event)
        topic, payload, qos, retain, live_only = service.publish_queue.get_nowait()
        self.assertTrue(live_only)
        self.assertEqual(qos, 0)
        self.assertIn('"packet_type":"H1"', payload)

    def test_fault_event_is_replayable_qos1(self):
        service, _ = self.make_service()
        event = GatewayEvent(
            event_type="fault",
            gateway_id="gw-01",
            node_id="001A",
            packet_type="E2",
            payload="E2|001A|...",
        )
        service.publish_event(event)
        topic, payload, qos, retain, live_only = service.publish_queue.get_nowait()
        self.assertFalse(live_only)
        self.assertEqual(qos, 1)
        self.assertEqual(topic, "s3/zigbee/gw-01/event/001A")

    def test_connect_subscribes_and_publishes_online_status(self):
        service, client = self.make_service()
        service._on_connect(client, None, None, 0)
        self.assertIn(("s3/zigbee/gw-01/cmd", 1), client.subscriptions)
        self.assertIn(("s3/zigbee/gw-01/node/+/cmd", 1), client.subscriptions)
        topic, raw, qos, retain = client.published[0]
        self.assertEqual(topic, "s3/zigbee/gw-01/status")
        self.assertEqual(json.loads(raw)["status"], "online")
        self.assertEqual(qos, 1)
        self.assertTrue(retain)

    def test_every_successful_connect_republishes_gateway_online_status(self):
        service, client = self.make_service()

        service._on_connect(client, None, None, 0)
        service.connected.clear()
        service._on_connect(client, None, None, 0)

        status_messages = [
            item
            for item in client.published
            if item[0] == "s3/zigbee/gw-01/status"
        ]
        self.assertEqual(len(status_messages), 2)
        for topic, raw, qos, retain in status_messages:
            self.assertEqual(topic, "s3/zigbee/gw-01/status")
            self.assertEqual(json.loads(raw)["status"], "online")
            self.assertEqual(json.loads(raw)["gateway_id"], "gw-01")
            self.assertEqual(qos, 1)
            self.assertTrue(retain)

    def test_status_heartbeat_republishes_online_while_connected(self):
        service, client = self.make_service(status_interval_seconds=1)
        service.connected.set()
        worker = threading.Thread(target=service._status_heartbeat_worker, daemon=True)
        worker.start()
        time.sleep(1.2)
        service.stopping.set()
        worker.join(timeout=1)

        status_messages = [
            item for item in client.published if item[0] == "s3/zigbee/gw-01/status"
        ]
        self.assertGreaterEqual(len(status_messages), 1)
        topic, raw, qos, retain = status_messages[-1]
        self.assertEqual(topic, "s3/zigbee/gw-01/status")
        self.assertEqual(json.loads(raw)["status"], "online")
        self.assertEqual(qos, 1)
        self.assertTrue(retain)

    def test_status_heartbeat_skips_publish_while_disconnected(self):
        service, client = self.make_service(status_interval_seconds=1)
        worker = threading.Thread(target=service._status_heartbeat_worker, daemon=True)
        worker.start()
        time.sleep(1.2)
        service.stopping.set()
        worker.join(timeout=1)
        self.assertEqual(client.published, [])

    def test_command_callback_is_transport_agnostic(self):
        service, client = self.make_service()
        received = []
        service.set_command_handler(received.append)

        class Msg:
            topic = "s3/zigbee/gw-01/cmd"
            payload = b'{"request_id":"r1","command":"poll"}'

        service._on_message(client, None, Msg())
        self.assertEqual(received[0]["command"], "poll")
        self.assertEqual(received[0]["source_topic"], Msg.topic)

    def test_mirroring_queue_preserves_http_queue_and_mirrors_packet(self):
        http_queue = FakeQueue()
        queue = MQTTMirroringQueue(http_queue, packet_type="H1")
        item = ("001A", b"#H1|001A|...", 0)

        with patch(
            "pyserialgateway.mqtt_service.mirroring.mirror_validated_packet"
        ) as mirror:
            result = queue.put(item, True, timeout=0.25)

        self.assertEqual(result, "http-queue-result")
        self.assertEqual(http_queue.items, [(item, (True,), {"timeout": 0.25})])
        mirror.assert_called_once_with(
            node_id="001A",
            node_data=b"#H1|001A|...",
            packet_type="H1",
        )

    def test_mirroring_failure_does_not_break_http_queue(self):
        http_queue = FakeQueue()
        queue = MQTTMirroringQueue(http_queue, packet_type="E2")
        item = ("00FF", b"#E2|00FF|...", 0)

        with patch(
            "pyserialgateway.mqtt_service.mirroring.mirror_validated_packet",
            side_effect=RuntimeError("mqtt unavailable"),
        ):
            result = queue.put(item)

        self.assertEqual(result, "http-queue-result")
        self.assertEqual(http_queue.items[0][0], item)


if __name__ == "__main__":
    unittest.main()
