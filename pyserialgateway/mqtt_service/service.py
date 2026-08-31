"""Shared MQTT transport used by both S3 Zigbee gateway implementations."""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import queue
import ssl
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from .buffer import MQTTBuffer
from .config import MQTTConfig
from .events import GatewayEvent
from .topics import MQTTTopics


_LOG = logging.getLogger("S3MQTT")


def _configure_mqtt_file_logging(config: MQTTConfig) -> None:
    """Attach one dedicated rotating file handler to the S3MQTT logger."""
    log_path = os.path.abspath(config.log_file)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    for handler in _LOG.handlers:
        if getattr(handler, "_s3_mqtt_log_path", None) == log_path:
            return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    handler._s3_mqtt_log_path = log_path
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"
        )
    )
    _LOG.setLevel(logging.INFO)
    _LOG.addHandler(handler)


class MQTTService:
    """Asynchronous MQTT transport with reconnect, buffering, LWT and commands."""

    LIVE_ONLY_TYPES = {"heartbeat", "telemetry", "node_packet"}

    def __init__(self, config: Optional[MQTTConfig] = None, client=None):
        self.config = config or MQTTConfig.from_env()
        _configure_mqtt_file_logging(self.config)
        self.topics = MQTTTopics(self.config.topic_root, self.config.gateway_id)
        self.client = client or mqtt.Client(client_id=f"s3-{self.config.gateway_id}")
        self.connected = threading.Event()
        self.stopping = threading.Event()
        self.publish_queue = queue.Queue()
        self.command_handler: Optional[Callable[[dict], None]] = None
        self.worker_thread = None
        self.connect_thread = None
        self.buffer = MQTTBuffer(
            self.config.buffer_db, self.config.buffer_retention_days
        )
        self._configure_client()

    def _configure_client(self) -> None:
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if self.config.username:
            self.client.username_pw_set(
                self.config.username, self.config.password or None
            )

        if self.config.tls:
            self.client.tls_set(
                ca_certs=self.config.ca_cert,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self.client.tls_insecure_set(self.config.tls_insecure)

        offline = json.dumps(
            {
                "status": "offline",
                "gateway_id": self.config.gateway_id,
                "gateway_type": "s3_zigbee",
            },
            separators=(",", ":"),
        )
        self.client.will_set(self.topics.status(), offline, qos=1, retain=True)

    def set_command_handler(self, handler: Callable[[dict], None]) -> None:
        self.command_handler = handler

    def start(self) -> None:
        if not self.config.enabled:
            _LOG.info("MQTT disabled by configuration")
            return
        self.config.validate()
        if self.worker_thread and self.worker_thread.is_alive():
            return
        _LOG.info(
            "MQTT service starting gateway_id=%s broker=%s:%s tls=%s",
            self.config.gateway_id,
            self.config.broker,
            self.config.port,
            self.config.tls,
        )
        self.stopping.clear()
        self.worker_thread = threading.Thread(
            target=self._publish_worker, name="S3MQTTPublish", daemon=True
        )
        self.worker_thread.start()
        self.connect_thread = threading.Thread(
            target=self._connect_with_backoff, name="S3MQTTConnect", daemon=True
        )
        self.connect_thread.start()

    def stop(self) -> None:
        self.stopping.set()
        if not self.config.enabled:
            return
        try:
            if self.connected.is_set():
                self._publish_now(
                    self.topics.status(),
                    json.dumps(
                        {
                            "status": "offline",
                            "gateway_id": self.config.gateway_id,
                            "gateway_type": "s3_zigbee",
                        },
                        separators=(",", ":"),
                    ),
                    qos=1,
                    retain=True,
                )
            self.client.disconnect()
            self.client.loop_stop()
        finally:
            self.connected.clear()
            _LOG.info("MQTT service stopped gateway_id=%s", self.config.gateway_id)

    def publish_event(self, event: GatewayEvent) -> None:
        node_id = str(event.node_id or "gateway")
        topic = self.topics.for_event(event.event_type, node_id)
        payload = json.dumps(event.to_dict(), separators=(",", ":"), default=str)
        live_only = event.event_type.strip().lower() in self.LIVE_ONLY_TYPES
        qos = 0 if live_only else 1
        self.publish_queue.put((topic, payload, qos, False, live_only))
        _LOG.info(
            "MQTT event queued event_type=%s node_id=%s topic=%s qos=%s live_only=%s",
            event.event_type,
            node_id,
            topic,
            qos,
            live_only,
        )

    def publish_json(
        self,
        topic: str,
        payload: dict,
        qos: int = 1,
        retain: bool = False,
        live_only: bool = False,
    ) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), default=str)
        self.publish_queue.put((topic, encoded, qos, retain, live_only))
        _LOG.info(
            "MQTT JSON queued topic=%s qos=%s retain=%s live_only=%s",
            topic,
            qos,
            retain,
            live_only,
        )

    def publish_command_result(self, request_id: str, payload: dict) -> None:
        self.publish_json(self.topics.command_result(request_id), payload, qos=1)

    def _connect_with_backoff(self) -> None:
        delay = 2
        while not self.stopping.is_set() and not self.connected.is_set():
            try:
                _LOG.info(
                    "MQTT connecting broker=%s:%s keepalive=%s",
                    self.config.broker,
                    self.config.port,
                    self.config.keepalive,
                )
                self.client.connect(
                    self.config.broker,
                    self.config.port,
                    self.config.keepalive,
                )
                self.client.loop_start()
                if self.connected.wait(timeout=5):
                    return
            except Exception as exc:
                _LOG.warning("MQTT connection failed: %s", exc)
            _LOG.info("MQTT reconnect retry in %ss", delay)
            self.stopping.wait(delay)
            delay = min(delay * 2, 60)

    def _on_connect(self, client, userdata, flags, rc, *args) -> None:
        if rc != 0:
            _LOG.error("MQTT connect rejected rc=%s", rc)
            return
        self.connected.set()
        client.subscribe(self.topics.command(), qos=1)
        client.subscribe(self.topics.node_command(), qos=1)
        _LOG.info(
            "MQTT connected gateway_id=%s command_topic=%s node_command_topic=%s",
            self.config.gateway_id,
            self.topics.command(),
            self.topics.node_command(),
        )
        self._publish_now(
            self.topics.status(),
            json.dumps(
                {
                    "status": "online",
                    "gateway_id": self.config.gateway_id,
                    "gateway_type": "s3_zigbee",
                },
                separators=(",", ":"),
            ),
            qos=1,
            retain=True,
        )
        self._replay_buffer()

    def _on_disconnect(self, client, userdata, rc, *args) -> None:
        self.connected.clear()
        _LOG.warning("MQTT disconnected rc=%s", rc)
        if not self.stopping.is_set():
            threading.Thread(
                target=self._connect_with_backoff,
                name="S3MQTTReconnect",
                daemon=True,
            ).start()

    def _on_message(self, client, userdata, msg) -> None:
        try:
            decoded = msg.payload.decode("utf-8")
            data = json.loads(decoded)
            if not isinstance(data, dict):
                raise ValueError("MQTT command payload must be a JSON object")
            data.setdefault("source_topic", msg.topic)
            _LOG.info(
                "MQTT command received topic=%s request_id=%s command=%s",
                msg.topic,
                data.get("request_id", "-"),
                data.get("command", "-"),
            )
            if self.command_handler is not None:
                self.command_handler(data)
        except Exception as exc:
            _LOG.error("Invalid MQTT command on %s: %s", msg.topic, exc)

    def _publish_worker(self) -> None:
        while not self.stopping.is_set():
            try:
                topic, payload, qos, retain, live_only = self.publish_queue.get(
                    timeout=0.5
                )
            except queue.Empty:
                continue
            try:
                if not self.connected.is_set():
                    if not live_only:
                        self.buffer.put(topic, payload, qos, retain)
                        _LOG.info("MQTT message buffered topic=%s qos=%s", topic, qos)
                    else:
                        _LOG.info("MQTT live-only message dropped while offline topic=%s", topic)
                    continue
                if not self._publish_now(topic, payload, qos, retain) and not live_only:
                    self.buffer.put(topic, payload, qos, retain)
                    _LOG.info("MQTT failed publish buffered topic=%s qos=%s", topic, qos)
            finally:
                self.publish_queue.task_done()

    def _publish_now(self, topic: str, payload: str, qos: int, retain: bool) -> bool:
        try:
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            success = result.rc == mqtt.MQTT_ERR_SUCCESS
            if success:
                _LOG.info(
                    "MQTT published topic=%s qos=%s retain=%s",
                    topic,
                    qos,
                    retain,
                )
            else:
                _LOG.warning("MQTT publish returned rc=%s topic=%s", result.rc, topic)
            return success
        except Exception as exc:
            _LOG.warning("MQTT publish failed topic=%s: %s", topic, exc)
            return False

    def _replay_buffer(self) -> None:
        self.buffer.cleanup()
        pending = list(self.buffer.pending())
        if pending:
            _LOG.info("MQTT replaying %s buffered message(s)", len(pending))
        for message_id, topic, payload, qos, retain in pending:
            if not self.connected.is_set():
                break
            if self._publish_now(topic, payload, qos, retain):
                self.buffer.delete(message_id)
                _LOG.info("MQTT replay complete message_id=%s topic=%s", message_id, topic)
            else:
                break
