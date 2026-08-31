"""Environment-driven configuration for the shared MQTT transport."""

from dataclasses import dataclass
import os
import socket


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MQTTConfig:
    enabled: bool = True
    broker: str = "localhost"
    port: int = 8883
    username: str = ""
    password: str = ""
    keepalive: int = 60
    tls: bool = True
    ca_cert: str = ""
    tls_insecure: bool = False
    gateway_id: str = ""
    topic_root: str = "s3/zigbee"
    buffer_db: str = "mqtt_buffer.db"
    buffer_retention_days: int = 7

    @classmethod
    def from_env(cls) -> "MQTTConfig":
        return cls(
            enabled=_env_bool("MQTT_ENABLED", True),
            broker=os.getenv("MQTT_BROKER", "localhost"),
            port=int(os.getenv("MQTT_PORT", "8883")),
            username=os.getenv("MQTT_USERNAME", ""),
            password=os.getenv("MQTT_PASSWORD", ""),
            keepalive=int(os.getenv("MQTT_KEEPALIVE", "60")),
            tls=_env_bool("MQTT_TLS", True),
            ca_cert=os.getenv("MQTT_CA_CERT", ""),
            tls_insecure=_env_bool("MQTT_TLS_INSECURE", False),
            gateway_id=os.getenv("GATEWAY_ID", socket.gethostname()),
            topic_root=os.getenv("MQTT_TOPIC_ROOT", "s3/zigbee").strip("/"),
            buffer_db=os.getenv("MQTT_BUFFER_DB", "mqtt_buffer.db"),
            buffer_retention_days=int(os.getenv("MQTT_BUFFER_RETENTION_DAYS", "7")),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if not self.broker:
            raise ValueError("MQTT_BROKER must not be empty")
        if not self.gateway_id:
            raise ValueError("GATEWAY_ID must not be empty")
        if self.tls and not self.ca_cert:
            raise ValueError("MQTT_CA_CERT is required when MQTT_TLS=true")
