# S3 Zigbee Gateway - Operator Guide

The normal site operator works only from:

```text
/home/pi/S3Gateway/
```

## Operator files

- `samplelist.csv` - complete site node inventory.
- `pygw_conf.py` - site gateway configuration, including gateway node ID, PAN ID and Zigbee channel.
- `log/` - gateway, MQTT and error logs.
- `GPSlog/` - daily GPS scan KML files for retrieval or Google Earth.
- `README-OPERATOR.md` - this guide.

Do not edit files directly under `/opt/s3-gateway/app/` during normal operation. The DBUP command copies validated operator files into the protected runtime.

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

The node inventory must use the intended PAN ID/channel for the Zigbee network to which the nodes belong.

## Apply operator changes

After changing `samplelist.csv` and/or `pygw_conf.py`, run:

```bash
sudo s3-gateway-dbup
```

The command validates the files, backs up PostgreSQL and production configuration, synchronizes the database using `DBUP_ONLY`, restarts the gateway, and verifies that the service becomes active.

## Check gateway status

```bash
sudo systemctl status s3-zigbee-gateway
```

Expected:

```text
Active: active (running)
```

The production deployment manages `GPSUP` through a systemd drop-in. Confirm the effective startup command with:

```bash
sudo systemctl show s3-zigbee-gateway -p ExecStart
ps -ef | grep '[p]ygw_main.py'
```

Expected process arguments include:

```text
pygw_main.py GPSUP
```

Do not remove or edit the systemd GPSUP drop-in during normal operation.

## Check node count and PAN/channel

```bash
sudo -u s3gw psql -d "serial-gateway-program" -c \
"SELECT pan_id, channel, COUNT(*) FROM node_database GROUP BY pan_id, channel ORDER BY pan_id, channel;"
```

## Check gateway logs

Gateway:

```bash
tail -n 50 ~/S3Gateway/log/gateway.log
```

MQTT:

```bash
tail -n 30 ~/S3Gateway/log/mqtt.log
```

Errors:

```bash
tail -n 50 ~/S3Gateway/log/error.log
```

## Retrieve GPS logs

Daily GPS scans are stored as KML files under:

```text
~/S3Gateway/GPSlog/
```

List available scans:

```bash
ls -lh ~/S3Gateway/GPSlog/
```

Show the newest GPS scan:

```bash
ls -1t ~/S3Gateway/GPSlog/*_GPSscan.kml | head -1
```

The production runtime keeps using its legacy path:

```text
/opt/s3-gateway/app/PYSerialGateway/GPSlog
```

but deployment maps that path to the operator workspace. Verify it with:

```bash
readlink -f /opt/s3-gateway/app/PYSerialGateway/GPSlog
```

Expected:

```text
/home/pi/S3Gateway/GPSlog
```

## Hardware reset recovery

The gateway can reset its CP210x USB interface when serial recovery is required. The deployment installs a restricted sudo rule allowing the `s3gw` service account to run only the approved hardware-reset command as root.

Check the rule:

```bash
sudo visudo -cf /etc/sudoers.d/s3-gateway-hwreset
sudo -u s3gw sudo -n -l
```

The rule must be limited to:

```text
/usr/bin/python3 /opt/s3-gateway/app/pyserialgateway/hardware_reset.py
```

Do not grant broad `NOPASSWD: ALL` access to `s3gw`.

The privileged reset script and its configuration are deployment-protected. Operators must not modify:

```text
/opt/s3-gateway/app/pyserialgateway/hardware_reset.py
/opt/s3-gateway/app/pyserialgateway/config_PYproperties.py
```

## Production deployment validation

After an approved production deployment, verify:

```bash
sudo systemctl is-active s3-zigbee-gateway
ps -ef | grep '[p]ygw_main.py'
readlink -f /opt/s3-gateway/app/PYSerialGateway/GPSlog
sudo -u s3gw test -w ~/S3Gateway/GPSlog && echo "GPS write PASS"
sudo visudo -cf /etc/sudoers.d/s3-gateway-hwreset
systemctl is-active s3-gateway-log-maintenance.timer
```

Expected results are an active gateway, `pygw_main.py GPSUP`, the GPS path resolving to `/home/pi/S3Gateway/GPSlog`, GPS write access for `s3gw`, a valid restricted sudoers file, and an active log-maintenance timer.

## Operator rules

- Normal edits are made only in `~/S3Gateway/samplelist.csv` and `~/S3Gateway/pygw_conf.py`.
- Operational logs and GPS KML files are read from `~/S3Gateway/log/` and `~/S3Gateway/GPSlog/`.
- Always keep `samplelist.csv` as the complete desired site inventory.
- Run `sudo s3-gateway-dbup` after node or gateway network changes.
- Do not run `DBUP` or `DBUP_ONLY` manually while the production service is active.
- Do not edit `/opt/s3-gateway/app/PYSerialGateway/pygw_conf.py` directly during normal operation.
- Do not modify `pyserialgateway/`, `.venv/`, systemd service/drop-in files, sudoers files, or PostgreSQL manually unless performing approved maintenance.
