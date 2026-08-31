"""Mirror validated gateway packets to MQTT without changing HTTP queue semantics."""

import logging
import os
import threading
from typing import Any, Optional

from .adapters import RefactoredGatewayMQTTAdapter
from .config import MQTTConfig
from .service import MQTTService


_LOG = logging.getLogger("S3MQTTMirror")
_LOCK = threading.Lock()
_ADAPTER: Optional[RefactoredGatewayMQTTAdapter] = None
_START_FAILED = False


def _mqtt_requested() -> bool:
    """Require an explicit MQTT_ENABLED=true for runtime gateway integration."""
    value = os.getenv("MQTT_ENABLED", "false")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_adapter() -> Optional[RefactoredGatewayMQTTAdapter]:
    global _ADAPTER, _START_FAILED

    if _ADAPTER is not None:
        return _ADAPTER
    if _START_FAILED or not _mqtt_requested():
        return None

    with _LOCK:
        if _ADAPTER is not None:
            return _ADAPTER
        if _START_FAILED:
            return None

        try:
            config = MQTTConfig.from_env()
            config.validate()
            service = MQTTService(config)
            adapter = RefactoredGatewayMQTTAdapter(
                service=service,
                gateway_id=config.gateway_id,
            )
            adapter.start()
            _ADAPTER = adapter
            _LOG.info(
                "MQTT mirroring started gateway_id=%s broker=%s:%s",
                config.gateway_id,
                config.broker,
                config.port,
            )
        except Exception:
            _START_FAILED = True
            _LOG.exception("MQTT mirroring failed to start; HTTP path remains active")
            return None

    return _ADAPTER


def mirror_validated_packet(
    node_id: str,
    node_data: Any,
    packet_type: Optional[str] = None,
) -> None:
    """Queue a validated packet for MQTT publication.

    This function never raises into the existing serial/DB/HTTP processing path.
    MQTTService.publish_event() only enqueues work; network I/O occurs on the
    service's background worker.
    """
    adapter = _get_adapter()
    if adapter is None:
        return

    try:
        adapter.publish_validated_packet(
            node_id=str(node_id),
            node_data=node_data,
            packet_type=packet_type,
            event_type="node_packet",
        )
    except Exception:
        _LOG.exception(
            "MQTT mirror enqueue failed node_id=%s packet_type=%s",
            node_id,
            packet_type,
        )


class MQTTMirroringQueue:
    """Queue proxy preserving the existing HTTP queue while mirroring to MQTT."""

    def __init__(self, queue_obj, packet_type: Optional[str] = None):
        self._queue = queue_obj
        self._packet_type = packet_type

    def put(self, item, *args, **kwargs):
        # Preserve the established HTTP behavior first.
        result = self._queue.put(item, *args, **kwargs)

        # Existing DatabaseThread payload shape:
        #   (node_id, node_data, flag)
        try:
            node_id = item[0]
            node_data = item[1]
            mirror_validated_packet(
                node_id=node_id,
                node_data=node_data,
                packet_type=self._packet_type,
            )
        except Exception:
            _LOG.exception("Unable to mirror validated queue item to MQTT")

        return result

    def __getattr__(self, name):
        return getattr(self._queue, name)
