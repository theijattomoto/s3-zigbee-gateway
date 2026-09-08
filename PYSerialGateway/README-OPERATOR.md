# S3 Zigbee Gateway - Operator Guide

This folder is the operator-facing area for normal site operation.

## Operator files

- `samplelist.csv` - site node inventory used for commissioning.
- `run-service.sh` - gateway launcher used by systemd and maintenance commands.
- `log/` - gateway and MQTT logs.
- `errorlog/` - gateway error logs.

Do not edit files under `../pyserialgateway/`. That folder contains application source code maintained by developers.

## Add or update nodes

1. Edit the complete site inventory:

```bash
nano ~/gateway-test/s3-zigbee-gateway/PYSerialGateway/samplelist.csv
```

CSV format:

```csv
pole_node,node,pan_id,channel
R1-1,2001,1001,20
SP_TEST1,7468,1001,20
```

Important: `samplelist.csv` is the desired site inventory. Do not replace it with a file containing only the new node. Nodes missing from the CSV may be removed from the gateway database during DB synchronization.

2. Run the commissioning command:

```bash
sudo s3-gateway-dbup
```

The command automatically:

- validates `samplelist.csv`;
- backs up PostgreSQL;
- stops the production gateway service;
- runs one-time database synchronization;
- exits commissioning mode automatically;
- restarts the production gateway service.

A successful run should include:

```text
CSV validation: PASS
DBUP_ONLY completed. Database synchronized; exiting before gateway runtime starts.
DBUP: PASS
Starting production gateway...
```

## Check gateway status

```bash
sudo systemctl status s3-zigbee-gateway
```

Expected status:

```text
Active: active (running)
```

## Check MQTT activity

```bash
tail -n 20 ~/gateway-test/s3-zigbee-gateway/PYSerialGateway/log/mqtt.log
```

Normal production logs should show the MQTT broker connected and heartbeat packets published.

## Check gateway logs

```bash
tail -n 50 ~/gateway-test/s3-zigbee-gateway/PYSerialGateway/log/gateway.log
```

Errors:

```bash
tail -n 50 ~/gateway-test/s3-zigbee-gateway/PYSerialGateway/errorlog/error.log
```

## Operator rules

- Edit only `PYSerialGateway/samplelist.csv` for normal node commissioning.
- Use `sudo s3-gateway-dbup` after changing the node inventory.
- Do not run `DBUP` manually during normal production operation.
- Do not run the gateway with `sudo ./run-service.sh`.
- Do not modify `pyserialgateway/`, `.venv/`, `.git/`, or systemd service files unless performing approved maintenance.
- Do not use `git reset --hard` on the production gateway because the site `samplelist.csv` is intentionally kept as a local site-specific file.
