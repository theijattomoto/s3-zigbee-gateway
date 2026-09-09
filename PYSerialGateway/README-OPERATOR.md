# S3 Zigbee Gateway - Operator Guide

The normal site operator works only from:

```text
/home/pi/S3Gateway/
```

## Operator files

- `samplelist.csv` - complete site node inventory.
- `pygw_conf.py` - site gateway configuration, including gateway node ID, PAN ID and Zigbee channel.
- `README-OPERATOR.md` - this guide.

Do not edit files directly under `/opt/s3-gateway/app/` during normal operation. The DBUP command copies the validated operator files into the protected runtime.

## Node inventory

Edit:

```bash
nano ~/S3Gateway/samplelist.csv
```

Format:

```csv
pole_node,node,pan_id,channel
R-1,8EED,1001,11
R-2,8EEE,1001,11
```

`samplelist.csv` is the complete desired node inventory. Nodes missing from this file may be removed from PostgreSQL during DB synchronization.

To add a node, add a new row. To remove a node, remove its row. To change a node PAN ID or channel, edit the corresponding row.

## Gateway PAN ID and channel

Edit:

```bash
nano ~/S3Gateway/pygw_conf.py
```

For normal site commissioning, the main values are:

```python
first_GW_data = ('FE01', '1001', '11')
second_GW_data = ('FE02', '1001', '11')
```

Tuple format:

```text
(gateway_node_id, pan_id, channel)
```

Example:

```python
first_GW_data = ('FE01', '1001', '15')
second_GW_data = ('FE02', '1001', '15')
```

The node inventory must use the intended PAN ID/channel for the Zigbee network to which the nodes belong.

## Apply operator changes

After changing `samplelist.csv` and/or `pygw_conf.py`, run:

```bash
sudo s3-gateway-dbup
```

The command automatically:

- validates `samplelist.csv`;
- validates `pygw_conf.py` and the gateway tuples;
- backs up PostgreSQL;
- backs up the current production `samplelist.csv` and `pygw_conf.py`;
- copies the operator files into the protected runtime;
- stops the production gateway service;
- runs `DBUP_ONLY` using PostgreSQL user `s3gw`;
- restarts the production gateway service;
- verifies that the service becomes active.

A successful run should include output similar to:

```text
CSV validation: PASS
Gateway config validation: PASS
DBUP_ONLY completed. Database synchronized; exiting before gateway runtime starts.
DBUP: PASS
Starting production gateway...
```

## Check gateway status

```bash
sudo systemctl status s3-zigbee-gateway
```

Expected:

```text
Active: active (running)
```

## Check node count and PAN/channel

```bash
sudo -u s3gw psql -d "serial-gateway-program" -c \
"SELECT pan_id, channel, COUNT(*) FROM node_database GROUP BY pan_id, channel ORDER BY pan_id, channel;"
```

## Check gateway logs

```bash
sudo tail -n 50 /opt/s3-gateway/app/PYSerialGateway/log/gateway.log
```

MQTT:

```bash
sudo tail -n 30 /opt/s3-gateway/app/PYSerialGateway/log/mqtt.log
```

Errors:

```bash
sudo tail -n 50 /opt/s3-gateway/app/PYSerialGateway/errorlog/error.log
```

## Operator rules

- Normal edits are made only in `~/S3Gateway/samplelist.csv` and `~/S3Gateway/pygw_conf.py`.
- Always keep `samplelist.csv` as the complete desired site inventory.
- Run `sudo s3-gateway-dbup` after node or gateway network changes.
- Do not run `DBUP` or `DBUP_ONLY` manually while the production service is active.
- Do not edit `/opt/s3-gateway/app/PYSerialGateway/pygw_conf.py` directly during normal operation.
- Do not modify `pyserialgateway/`, `.venv/`, systemd service files, or PostgreSQL manually unless performing approved maintenance.
