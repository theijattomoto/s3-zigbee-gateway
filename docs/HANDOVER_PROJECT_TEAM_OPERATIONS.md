# S3 Zigbee Gateway — Project Team Operations Handover

## Purpose

This SOP is for the Project Team responsible for day-to-day operation of an installed S3 Zigbee Gateway.

The Project Team operates the gateway. It does **not** install application code, modify the protected runtime, change the database schema, or perform software development.

## Supported operating model

Normal operator work is performed from:

```text
/home/pi/S3Gateway/
```

Operator-managed files and outputs:

```text
/home/pi/S3Gateway/
├── samplelist.csv
├── pygw_conf.py
├── README-OPERATOR.md
├── log/
│   ├── gateway.log
│   ├── mqtt.log
│   └── error.log
└── GPSlog/
```

Protected production runtime:

```text
/opt/s3-gateway/app/
```

Do not edit the protected production runtime during normal operation.

---

## 1. Check gateway status

Run:

```bash
sudo systemctl status s3-zigbee-gateway
```

Quick check:

```bash
sudo systemctl is-active s3-zigbee-gateway
```

Expected:

```text
active
```

Confirm the production process is running with GPS mapping enabled:

```bash
ps -ef | grep '[p]ygw_main.py'
```

Expected command arguments include:

```text
pygw_main.py GPSUP
```

Check the effective systemd command:

```bash
sudo systemctl show s3-zigbee-gateway -p ExecStart
```

---

## 2. Start, stop and restart the gateway

Restart:

```bash
sudo systemctl restart s3-zigbee-gateway
```

Stop:

```bash
sudo systemctl stop s3-zigbee-gateway
```

Start:

```bash
sudo systemctl start s3-zigbee-gateway
```

After a restart, always confirm:

```bash
sudo systemctl is-active s3-zigbee-gateway
ps -ef | grep '[p]ygw_main.py'
```

Do not manually launch `pygw_main.py` while the systemd service is running.

---

## 3. Manage the site node list

The complete desired node inventory is:

```text
~/S3Gateway/samplelist.csv
```

Edit it with:

```bash
nano ~/S3Gateway/samplelist.csv
```

Required format:

```csv
pole_node,node,pan_id,channel
R-1,8EED,1001,11
R-2,8EEE,1001,11
```

Rules:

- `pole_node` must identify the physical pole/location.
- `node` must be a 4-character hexadecimal node ID.
- `pan_id` is the Zigbee PAN ID.
- `channel` must be Zigbee channel 11–26.
- A node ID must appear only once.
- A pole ID must appear only once.
- Keep this file as the **complete desired site inventory**, not only the latest changes.

### Add a node

Add one new CSV row with the correct pole ID, node ID, PAN ID and channel.

### Remove a node

Remove the complete row for that node.

### Change PAN ID/channel

Edit the node's row and make the corresponding gateway network configuration change if required.

Do not update PostgreSQL manually for normal node-list maintenance.

---

## 4. Manage gateway PAN ID and channel

Edit:

```bash
nano ~/S3Gateway/pygw_conf.py
```

The gateway network tuples use this format:

```python
first_GW_data = ('FE01', '1001', '11')
second_GW_data = ('FE02', '1001', '11')
```

Tuple fields are:

```text
(gateway_node_id, pan_id, channel)
```

The production gateway currently operates one active Zigbee USB gateway/process. Simultaneous multi-USB/multi-channel operation is **future development** and is not part of this handover.

---

## 5. Apply node/configuration changes with DBUP

After editing `samplelist.csv` and/or `pygw_conf.py`, run only the approved wrapper:

```bash
sudo s3-gateway-dbup
```

The wrapper performs validation before changing production, backs up PostgreSQL and the current site files, installs the operator files into the protected runtime, stops the gateway, runs one-shot `DBUP_ONLY`, restarts the gateway and verifies the service becomes active.

Do not run `DBUP` or `DBUP_ONLY` manually while the production gateway service is active.

After DBUP:

```bash
sudo systemctl is-active s3-zigbee-gateway
```

Expected:

```text
active
```

Check node counts by PAN/channel:

```bash
sudo -u s3gw psql -d "serial-gateway-program" -c \
"SELECT pan_id, channel, COUNT(*) FROM node_database GROUP BY pan_id, channel ORDER BY pan_id, channel;"
```

---

## 6. Check gateway logs

Gateway runtime log:

```bash
tail -n 50 ~/S3Gateway/log/gateway.log
```

MQTT log:

```bash
tail -n 50 ~/S3Gateway/log/mqtt.log
```

Error log:

```bash
tail -n 50 ~/S3Gateway/log/error.log
```

Useful live monitoring:

```bash
tail -f ~/S3Gateway/log/gateway.log
```

Press `Ctrl+C` to stop watching the log.

### Normal indicators

Look for messages showing:

- Zigbee serial port connected.
- polling is running.
- node heartbeat packets are being processed.
- MQTT broker connected.
- MQTT transport ready.

### Escalate when

Escalate to IoT/Development if any of these persist after one controlled restart:

- service repeatedly exits or fails to start;
- Zigbee USB port cannot be detected;
- hardware reset repeatedly fails;
- MQTT cannot reconnect for an extended period while Internet connectivity is confirmed;
- PostgreSQL/DBUP fails;
- unexpected database corruption or duplicated node records;
- application traceback repeats continuously;
- a code change is required.

---

## 7. Check MQTT connectivity

Run:

```bash
tail -n 100 ~/S3Gateway/log/mqtt.log | \
grep -E 'broker connected|gateway status published|transport ready|disconnected|connection attempt'
```

Healthy startup normally includes:

```text
MQTT broker connected
MQTT gateway status published ... status=online
MQTT transport ready
```

Do not modify MQTT application code or broker configuration as part of normal Project Team operation.

---

## 8. Retrieve GPS KML files

GPS files are available at:

```text
~/S3Gateway/GPSlog/
```

List files:

```bash
ls -lh ~/S3Gateway/GPSlog/
```

Find the newest scan:

```bash
ls -1t ~/S3Gateway/GPSlog/*_GPSscan.kml | head -1
```

The protected runtime GPS path should resolve to the operator workspace:

```bash
readlink -f /opt/s3-gateway/app/PYSerialGateway/GPSlog
```

Expected:

```text
/home/pi/S3Gateway/GPSlog
```

---

## 9. Basic USB checks

Show USB serial devices:

```bash
ls -l /dev/ttyUSB*
```

Show CP210x USB converters:

```bash
lsusb | grep -i 'CP210'
```

Do not manually run the privileged hardware-reset script during normal operation unless directed by the IoT/Development team.

---

## 10. Controlled Raspberry Pi reboot

Before reboot:

```bash
sudo systemctl is-active s3-zigbee-gateway
```

Reboot:

```bash
sudo reboot
```

After reconnecting:

```bash
sudo systemctl is-enabled s3-zigbee-gateway
sudo systemctl is-active s3-zigbee-gateway
ps -ef | grep '[p]ygw_main.py'
```

Expected:

```text
enabled
active
... pygw_main.py GPSUP
```

---

## 11. Operator rules

Project Team may:

- start/stop/restart/check the gateway service;
- edit `~/S3Gateway/samplelist.csv`;
- edit approved site values in `~/S3Gateway/pygw_conf.py`;
- run `sudo s3-gateway-dbup`;
- read logs and GPS KML files;
- perform basic USB/service/network checks.

Project Team must not normally:

- edit `/opt/s3-gateway/app/`;
- edit Python application files;
- change the PostgreSQL schema;
- manually modify production database records;
- modify systemd service/drop-in files;
- modify `/etc/sudoers.d/s3-gateway-hwreset`;
- modify the production `.venv`;
- install a new gateway application version;
- implement multi-channel/dual-USB changes.

---

## 12. Handover acceptance — Project Team

The Project Team handover is accepted when the operator can independently demonstrate:

- [ ] Check gateway service status.
- [ ] Restart the gateway and confirm recovery.
- [ ] Identify the active `GPSUP` process.
- [ ] Read gateway, MQTT and error logs.
- [ ] Add a node correctly to `samplelist.csv`.
- [ ] Remove/change a node correctly in `samplelist.csv`.
- [ ] Identify PAN ID/channel configuration.
- [ ] Run `sudo s3-gateway-dbup` safely.
- [ ] Verify node counts after DBUP.
- [ ] Retrieve the latest GPS KML file.
- [ ] Identify when an issue must be escalated.

## Deferred / future work

The following are intentionally outside the current handover baseline:

- simultaneous two-USB/two-channel operation;
- new timetable/profile programming APIs;
- new MQTT command features;
- application code modification;
- database schema changes;
- Zigbee protocol/firmware development.
