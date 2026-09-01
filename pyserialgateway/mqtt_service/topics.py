"""MQTT topic construction for S3 Zigbee gateways."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MQTTTopics:
    topic_root: str
    gateway_id: str

    def _base(self) -> str:
        return f"{self.topic_root.strip('/')}/{self.gateway_id}"

    def status(self) -> str:
        return f"{self._base()}/status"

    def telemetry(self, node_id: str) -> str:
        return f"mainserver/node_zigbee/{self.gateway_id}/snode/heartbeat/{node_id}"

    def event(self, node_id: str) -> str:
        return f"{self._base()}/event/{node_id}"

    def gps(self, node_id: str) -> str:
        return f"{self._base()}/gps/{node_id}"

    def command(self) -> str:
        return f"{self._base()}/cmd"

    def node_command(self) -> str:
        return f"{self._base()}/node/+/cmd"

    def command_result(self, request_id: str) -> str:
        return f"{self._base()}/command_result/{request_id}"

    def for_event(self, event_type: str, node_id: str) -> str:
        normalized = (event_type or "event").strip().lower()
        if normalized in {"telemetry", "heartbeat", "node_packet"}:
            return self.telemetry(node_id)
        if normalized == "gps":
            return self.gps(node_id)
        return self.event(node_id)
