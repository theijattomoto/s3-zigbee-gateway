# Shared S3 Zigbee MQTT Service

This package is intentionally independent from both gateway implementations:

- legacy monolith: `pyserialgateway/PYGatewayListener.py_old`
- refactored package: `pyserialgateway/PYGatewayListener/`

It must not import serial, PostgreSQL, REST, recovery, polling, or listener modules.
Both implementations integrate through the same adapter contract.

## Bring MQTT up standalone first

Before wiring MQTT into either gateway implementation, validate the transport by
running it on its own from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Export the deployment values from `.env` into the current shell, or set them
with your service manager. The required minimum is:

```bash
export MQTT_ENABLED=true
export MQTT_BROKER='<broker-host-or-ip>'
export MQTT_PORT=8883
export MQTT_USERNAME='<username>'
export MQTT_PASSWORD='<password>'
export MQTT_TLS=true
export MQTT_CA_CERT='/path/to/broker-ca.crt'
export MQTT_TLS_INSECURE=false
export MQTT_TOPIC_ROOT='s3/zigbee'
export GATEWAY_ID='<unique-s3-gateway-id>'
```

Run a connection-only check:

```bash
python -m pyserialgateway.mqtt_service --timeout 15
```

Run a connection check and publish one synthetic event:

```bash
python -m pyserialgateway.mqtt_service --timeout 15 --publish-test
```

Keep the client online so command subscriptions and LWT behavior can be tested:

```bash
python -m pyserialgateway.mqtt_service --timeout 15 --publish-test --stay-alive
```

A successful connection prints `MQTT CONNECTED` and publishes retained `online`
state on `s3/zigbee/<gateway-id>/status`. A clean shutdown publishes retained
`offline` state. An unclean process/network failure should cause the broker to
publish the configured offline LWT.

Do not start gateway integration until this standalone smoke test passes.

## Runtime contract

```python
from pyserialgateway.mqtt_service import MQTTService
from pyserialgateway.mqtt_service.config import MQTTConfig
```

Create exactly one `MQTTService` per gateway process. The transport owns MQTT
connection state, TLS, reconnect/backoff, publish queue, LWT, subscriptions and
replayable buffering.

### Legacy monolith

```python
from pyserialgateway.mqtt_service import MQTTService, LegacyGatewayMQTTAdapter
from pyserialgateway.mqtt_service.config import MQTTConfig

mqtt_service = MQTTService(MQTTConfig.from_env())
mqtt_adapter = LegacyGatewayMQTTAdapter(
    mqtt_service,
    mqtt_service.config.gateway_id,
    command_sink=REST_controller_queue.put,
)
mqtt_adapter.start()

# Only after the monolith has accepted/validated a packet:
mqtt_adapter.publish_validated_packet(node_id, node_data, packet_type=ack)
```

### Refactored package

```python
from pyserialgateway.mqtt_service import MQTTService, RefactoredGatewayMQTTAdapter
from pyserialgateway.mqtt_service.config import MQTTConfig

mqtt_service = MQTTService(MQTTConfig.from_env())
mqtt_adapter = RefactoredGatewayMQTTAdapter(
    mqtt_service,
    mqtt_service.config.gateway_id,
    command_sink=REST_controller_queue.put,
)
mqtt_adapter.start()

# At the same validated-packet boundary used by the existing HTTP path:
mqtt_adapter.publish_validated_packet(node_id, node_data, packet_type=ack)
```

The adapters deliberately have the same API. Given the same validated packet,
they produce the same canonical `GatewayEvent` and therefore the same MQTT topic,
payload, QoS and buffering policy.

## Safety rules

1. Never publish directly from the raw serial read path.
2. Never let an MQTT callback write directly to the serial port.
3. Route commands through the gateway's existing command queue/serial writer.
4. MQTT failure must not block serial processing, PostgreSQL, polling, recovery,
   REST, or HTTP forwarding.
5. Heartbeat/telemetry is live-only and is not replayed after an outage.
6. Fault/event messages are QoS 1 and may be buffered/replayed.
7. Keep passwords outside Git; use environment variables.

## Topics

With `MQTT_TOPIC_ROOT=s3/zigbee` and `GATEWAY_ID=gw-01`:

- `s3/zigbee/gw-01/status`
- `s3/zigbee/gw-01/telemetry/{node_id}`
- `s3/zigbee/gw-01/event/{node_id}`
- `s3/zigbee/gw-01/gps/{node_id}`
- `s3/zigbee/gw-01/cmd`
- `s3/zigbee/gw-01/node/+/cmd`
- `s3/zigbee/gw-01/command_result/{request_id}`

The status topic uses retained QoS 1 online/offline messages and MQTT LWT.
