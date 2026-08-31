"""Canonical event types shared by legacy and refactored gateways."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GatewayEvent:
    event_type: str
    gateway_id: str
    node_id: Optional[str] = None
    packet_type: Optional[str] = None
    payload: Any = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "gateway_id": self.gateway_id,
            "node_id": self.node_id,
            "packet_type": self.packet_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
