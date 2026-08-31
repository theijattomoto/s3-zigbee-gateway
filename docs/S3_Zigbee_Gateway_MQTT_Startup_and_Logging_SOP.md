# S3 Zigbee Gateway
MQTT Startup & Logging SOP

Environment: Raspberry Pi gateway  |  Branch: feature/mqtt-gateway-integration

## 1. What starts when the gateway application starts

Running the gateway application starts the shared MQTT transport first. MQTT can remain connected even when no Zigbee USB/serial gateway is detected. The application then retries Zigbee serial discovery every 5 seconds instead of exiting.

```bash
python -m pyserialgateway.PYGatewayListener.main
```

## 2. Manual startup procedure

### 2.1 Open the project and activate the virtual environment

```bash
cd ~/gateway-test/s3-zigbee-gateway
source .venv/bin/activate
```

### 2.2 Load MQTT environment variables

Load the project .env without printing credentials to the terminal. The CA path below is the currently validated certificate path on the Raspberry Pi.

```bash
set -a
source .env
set +a

export MQTT_CA_CERT=/etc/s5/certs/server.crt
```

### 2.3 Start the gateway application

```bash
python -m pyserialgateway.PYGatewayListener.main
```

Expected behavior when no Zigbee gateway is attached:

```text
MQTT transport started independently of Zigbee serial.
No Zigbee gateway serial port detected. MQTT remains active; waiting for Zigbee gateway.
Waiting for Zigbee gateway serial port; retrying every 5.0s.
```

## 3. MQTT log

The dedicated rotating MQTT log is written to:

```text
log/mqtt.log
```

Watch it live from another terminal:

```bash
cd ~/gateway-test/s3-zigbee-gateway
tail -f log/mqtt.log
```

Healthy startup should show this lifecycle sequence:

```text
MQTT service starting gateway_id=s3-gw-01 ...
MQTT connection attempt broker=100.110.141.31:8883 ...
MQTT broker connected gateway_id=s3-gw-01 ...
MQTT gateway status published gateway_id=s3-gw-01 status=online ...
MQTT transport ready gateway_id=s3-gw-01
```

## 4. Gateway online/offline status

On every successful MQTT connection or reconnection, the gateway publishes a retained online status to:

```text
s3/zigbee/s3-gw-01/status
```

Current payload:

```json
{"status":"online","gateway_id":"s3-gw-01","gateway_type":"s3_zigbee"}
```

On graceful shutdown, it publishes the retained offline state before disconnecting:

```json
{"status":"offline","gateway_id":"s3-gw-01","gateway_type":"s3_zigbee"}
```

## 5. Stop the gateway application

In the terminal running the application, press `Ctrl+C`. A clean shutdown should show:

```text
MQTT gateway status published gateway_id=s3-gw-01 status=offline ...
MQTT disconnected cleanly gateway_id=s3-gw-01 rc=0
MQTT service stopped gateway_id=s3-gw-01
```

## 6. Is it configured to start on boot?

At present, auto-start is not proven. No systemd service file was found in the repository. Check the Raspberry Pi for an independently installed service using:

```bash
systemctl list-unit-files --type=service | grep -Ei 'zigbee|gateway|pygateway|s3'

systemctl list-units --type=service --all | grep -Ei 'zigbee|gateway|pygateway|s3'
```

If you already know a candidate service name, check it directly:

```bash
systemctl status <service-name>
systemctl is-enabled <service-name>
```

### Result interpretation

| Result | Meaning |
| --- | --- |
| `enabled` | Configured to start automatically at boot. |
| `disabled` | Service exists but does not auto-start. |
| `not-found` / no matching service | Gateway currently requires manual startup unless another startup mechanism is used. |

## 7. Recommended production boot arrangement

After the real Zigbee hardware path is validated, run the gateway under systemd. The service should start after networking is available, load MQTT settings from a protected environment file, restart automatically after crashes, and launch the virtual-environment Python interpreter directly.

> **Do not enable this yet.** Treat this unit as the recommended deployment target, not as proof of the current Raspberry Pi configuration. Validate the real Zigbee serial/hardware flow first, then install and enable the service deliberately.

```ini
[Unit]
Description=S3 Zigbee Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/gateway-test/s3-zigbee-gateway
EnvironmentFile=/home/pi/gateway-test/s3-zigbee-gateway/.env
Environment=MQTT_CA_CERT=/etc/s5/certs/server.crt
ExecStart=/home/pi/gateway-test/s3-zigbee-gateway/.venv/bin/python -m pyserialgateway.PYGatewayListener.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 8. Quick operational checks

| Check | Command / expected behavior |
| --- | --- |
| Gateway process | `pgrep -af "PYGatewayListener.main"` |
| MQTT lifecycle log | `tail -n 50 log/mqtt.log` |
| MQTT retained status | Subscribe to `s3/zigbee/s3-gw-01/status` using the broker client without placing the password literally in shell history. |
| Serial wait mode | Gateway process remains alive and logs serial retry every 30 seconds when hardware is absent. |

## Current status

Gateway/MQTT startup and lifecycle behavior validated on 1 Sep 2026. Auto-start on boot remains to be confirmed/configured on the Raspberry Pi.
