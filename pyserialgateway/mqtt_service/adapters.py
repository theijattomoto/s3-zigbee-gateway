"""Compatibility adapters for legacy monolithic and refactored gateways."""

from typing import Any, Callable, Optional

from .events import GatewayEvent


def _normalize_payload(value: Any) -> Any:
    """Convert gateway byte payloads to JSON-friendly UTF-8 text.

    Real PYGatewayListener packets are bytes. Decode them before they reach
    json.dumps so MQTT payloads contain the packet text itself rather than a
    Python representation such as ``b'...'``. Non-byte payloads are preserved.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="replace")
    return value


class _BaseGatewayMQTTAdapter:
    def __init__(self, service, gateway_id: str, command_sink: Optional[Callable[[dict], None]] = None):
        self.service = service
        self.gateway_id = gateway_id
        self.command_sink = command_sink

    def start(self) -> None:
        self.service.set_command_handler(self.handle_command)
        self.service.start()

    def stop(self) -> None:
        self.service.stop()

    def publish_validated_packet(
        self,
        node_id: str,
        node_data: Any,
        packet_type: Optional[str] = None,
        event_type: str = "node_packet",
    ) -> None:
        self.service.publish_event(
            GatewayEvent(
                event_type=event_type,
                gateway_id=self.gateway_id,
                node_id=str(node_id),
                packet_type=packet_type,
                payload=_normalize_payload(node_data),
            )
        )

    def handle_command(self, command: dict) -> None:
        if self.command_sink is not None:
            self.command_sink(command)


class LegacyGatewayMQTTAdapter(_BaseGatewayMQTTAdapter):
    """Thin adapter for PYGatewayListener.py_old."""


class RefactoredGatewayMQTTAdapter(_BaseGatewayMQTTAdapter):
    """Thin adapter for the PYGatewayListener package."""
