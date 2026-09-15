# S3 Zigbee Gateway — Production Team Build & Provisioning Handover

## Purpose

This SOP is for the Production Team that prepares a new S3 Zigbee Gateway from a blank Raspberry Pi and hands over a validated unit to the Project Team.

Production Team scope:

1. Install and prepare Raspberry Pi OS.
2. Create the required OS/service accounts and permissions.
3. Install system dependencies and PostgreSQL.
4. Obtain the approved gateway application source.
5. Create the Python virtual environment and install requirements.
6. Prepare the production runtime under `/opt/s3-gateway/app`.
7. Configure the site node list, gateway PAN/channel, environment and MQTT settings.
8. Install systemd/runtime hardening/log retention/operator access.
9. Connect the Zigbee USB gateway.
10. Validate the completed unit before handover.

The Production Team does **not** modify application source code. Code changes remain an IoT/Development responsibility.

---

## 1. Required inputs before production starts

Production must receive the following approved inputs:

- Raspberry Pi hardware and power supply.
- microSD/storage media.
- approved Raspberry Pi OS image/version.
- approved Git repository and branch/tag/commit.
- site `samplelist.csv`.
- site `pygw_conf.py` values.
- production `.env` values, including MQTT endpoint and credentials.
- required encrypted `required-<site>gw.zip` configuration bundle.
- Zigbee USB gateway hardware.
- gateway node ID, PAN ID and Zigbee channel.

Do not substitute development credentials or test broker settings into a production unit.

---

## 2. Install Raspberry Pi OS

Install the approved Raspberry Pi OS using the normal Production Team imaging process.

Minimum expected state after first boot:

```text
hostname configured
network connectivity available
SSH enabled if required by deployment policy
system clock/timezone correct
package manager working
pi operator account available
```

Recommended checks:

```bash
hostnamectl
ip addr
ip route
timedatectl
```

Update package metadata before application installation:

```bash
sudo apt update
sudo apt upgrade -y
```

Reboot if the OS/kernel update requires it:

```bash
sudo reboot
```

---

## 3. Install required OS packages

The gateway requires Python, PostgreSQL, Git and several deployment utilities.

Install:

```bash
sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-client \
  rsync \
  acl \
  sudo \
  usbutils
```

Verify:

```bash
python3 --version
git --version
psql --version
rsync --version | head -1
setfacl --version
lsusb --version
```

---

## 4. Create the gateway service account

The production service runs as the dedicated account:

```text
s3gw
```

Create it if it does not already exist:

```bash
id s3gw >/dev/null 2>&1 || \
  sudo useradd --system --create-home --shell /usr/sbin/nologin s3gw
```

Confirm:

```bash
id s3gw
```

Do not run the production gateway service as root.

---

## 5. Prepare PostgreSQL

Start and enable PostgreSQL:

```bash
sudo systemctl enable --now postgresql
sudo systemctl is-active postgresql
```

The current production runtime uses `DB_USER=s3gw`. Create a PostgreSQL role for the service account if required:

```bash
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='s3gw'" | grep -q 1 || \
sudo -u postgres createuser s3gw
```

Create the production database only on a **new gateway**. Do not recreate an existing production database during upgrade/repair work.

The repository `create_db.sql` is a baseline schema reference. It was originally written with database owner `pi`, so do not blindly execute it unchanged for the hardened `s3gw` production model.

For a new gateway, create the database owned by `s3gw`:

```bash
sudo -u postgres psql <<'SQL'
CREATE DATABASE "serial-gateway-program" OWNER s3gw;
SQL
```

Then create the required schema:

```bash
sudo -u postgres psql -d "serial-gateway-program" <<'SQL'
CREATE TABLE node_database (
    id          SERIAL PRIMARY KEY,
    pole_node   TEXT,
    node        TEXT NOT NULL,
    pan_id      TEXT,
    channel     TEXT,
    latitude    TEXT,
    longitude   TEXT,
    description TEXT
);

CREATE INDEX idx_node_database_node
    ON node_database (node);
CREATE INDEX idx_node_database_pan_channel
    ON node_database (pan_id, channel);

CREATE TABLE filter_time_py (
    id              SERIAL PRIMARY KEY,
    node            TEXT NOT NULL,
    ack             TEXT NOT NULL,
    dtime           TIMESTAMP,
    msgid           TEXT,
    oo_msgid        TEXT,
    dec_count       INTEGER DEFAULT 0,
    rollover_count  INTEGER DEFAULT 0,
    miss_count      INTEGER DEFAULT 0,
    override_flag   BOOLEAN,
    lamp_status     BOOLEAN
);

CREATE INDEX idx_filter_time_py_node_ack
    ON filter_time_py (node, ack);

ALTER TABLE node_database OWNER TO s3gw;
ALTER TABLE filter_time_py OWNER TO s3gw;
ALTER SEQUENCE node_database_id_seq OWNER TO s3gw;
ALTER SEQUENCE filter_time_py_id_seq OWNER TO s3gw;
SQL
```

Verify peer access as the service account:

```bash
sudo -u s3gw psql -d "serial-gateway-program" -c '\dt'
```

Expected tables:

```text
node_database
filter_time_py
```

---

## 6. Obtain the approved source

Use only the approved production branch/tag/commit supplied by IoT/Development.

Example:

```bash
mkdir -p ~/gateway-build
cd ~/gateway-build

git clone git@github.com:theijattomoto/s3-zigbee-gateway.git
cd s3-zigbee-gateway

git fetch origin
git checkout feature/daily-log-retention
git pull origin feature/daily-log-retention
```

Record the exact source revision used for the unit:

```bash
git status
git log -1 --oneline
```

Do not deploy with an uncommitted working tree:

```bash
git status --porcelain
```

Expected output: empty.

---

## 7. Prepare the production runtime

Create the runtime root:

```bash
sudo install -d -o root -g s3gw -m 755 /opt/s3-gateway
sudo install -d -o root -g s3gw -m 755 /opt/s3-gateway/app
sudo install -d -o root -g root -m 755 /opt/s3-gateway/backups
```

Copy the approved source into the initial runtime:

```bash
cd ~/gateway-build/s3-zigbee-gateway

sudo rsync -a --delete \
  --exclude=.git/ \
  ./ /opt/s3-gateway/app/
```

Set initial ownership:

```bash
sudo chown -R root:s3gw /opt/s3-gateway/app
```

---

## 8. Create the production Python environment

Create the virtual environment in the protected runtime:

```bash
sudo python3 -m venv /opt/s3-gateway/app/.venv
sudo /opt/s3-gateway/app/.venv/bin/pip install --upgrade pip
sudo /opt/s3-gateway/app/.venv/bin/pip install \
  -r /opt/s3-gateway/app/requirements.txt
```

Verify the important production imports:

```bash
/opt/s3-gateway/app/.venv/bin/python - <<'PY'
import psycopg2
import paho.mqtt.client
import serial
import flask
print('Python dependency check: PASS')
print('psycopg2:', psycopg2.__version__)
PY
```

---

## 9. Create the production environment file

Create from the repository example:

```bash
sudo cp /opt/s3-gateway/app/.env.example \
  /opt/s3-gateway/app/.env
```

Edit the production values:

```bash
sudo nano /opt/s3-gateway/app/.env
```

Minimum settings requiring production review include:

```text
DB_USER=s3gw
MQTT_ENABLED=true
MQTT_BROKER=<production broker>
MQTT_PORT=<production port>
MQTT_USERNAME=<approved username>
MQTT_PASSWORD=<approved password>
MQTT_TLS=<true/false per approved architecture>
MQTT_CA_CERT=<approved CA file when TLS is enabled>
MQTT_TOPIC_ROOT=s3/zigbee
GATEWAY_ID=<unique gateway ID>
MQTT_LOG_FILE=/home/pi/S3Gateway/log/mqtt.log
GATEWAY_LOG_DIR=/home/pi/S3Gateway/log
GATEWAY_ERROR_LOG_DIR=/home/pi/S3Gateway/log
```

Protect the file:

```bash
sudo chown root:s3gw /opt/s3-gateway/app/.env
sudo chmod 640 /opt/s3-gateway/app/.env
```

Never commit production passwords, certificates or secrets into Git.

---

## 10. Install site-specific configuration

Place the approved complete site node list at:

```text
/opt/s3-gateway/app/PYSerialGateway/samplelist.csv
```

Place the approved gateway configuration at:

```text
/opt/s3-gateway/app/PYSerialGateway/pygw_conf.py
```

The important gateway tuple format is:

```python
first_GW_data = ('FE01', '1001', '11')
second_GW_data = ('FE02', '1001', '11')
```

Format:

```text
(gateway_node_id, pan_id, channel)
```

Also confirm the required encrypted site gateway bundle exists under:

```text
/opt/s3-gateway/app/pyserialgateway/required-<site>gw.zip
```

The `cert_codename` in `pygw_conf.py` must match that bundle name.

---

## 11. Install the systemd service

The current repository manages the GPSUP **drop-in**, but the base systemd unit is still an installation prerequisite.

Create:

```bash
sudo tee /etc/systemd/system/s3-zigbee-gateway.service >/dev/null <<'EOF'
[Unit]
Description=S3 Zigbee Gateway
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

[Service]
Type=simple
User=s3gw
Group=s3gw
WorkingDirectory=/opt/s3-gateway/app/PYSerialGateway
EnvironmentFile=/opt/s3-gateway/app/.env
ExecStart=/opt/s3-gateway/app/PYSerialGateway/run-service.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Reload systemd:

```bash
sudo systemctl daemon-reload
sudo systemctl enable s3-zigbee-gateway
```

Do not start it yet; complete hardening and site setup first.

---

## 12. Run the approved deployment setup

Once `/opt/s3-gateway/app`, `.venv`, `.env` and the base systemd service exist, use the repository's deployment script to install the managed runtime state:

```bash
cd ~/gateway-build/s3-zigbee-gateway
sudo ./scripts/deploy-production.sh
```

This deployment path is responsible for:

- refreshing deploy-managed application code;
- preserving `.env`, `.venv`, site node list and site configuration;
- creating/refreshing the Project Team operator workspace;
- installing `s3-gateway-dbup`;
- configuring operator-facing logs;
- configuring GPS operator access;
- installing the GPSUP systemd drop-in;
- installing the restricted hardware-reset sudo rule;
- protecting the privileged reset code path;
- validating required runtime state;
- starting the gateway and verifying that it is active.

If deployment aborts, do not repeatedly rerun it without reviewing the reported failure.

---

## 13. Install log retention

Install the repository-managed log retention components:

```bash
cd ~/gateway-build/s3-zigbee-gateway
sudo bash scripts/install-log-retention.sh
```

Verify:

```bash
systemctl is-enabled s3-gateway-log-maintenance.timer
systemctl is-active s3-gateway-log-maintenance.timer
```

Expected:

```text
enabled
active
```

---

## 14. Initialize the node database using DBUP

After deployment, the Project Team operator files are available under:

```text
/home/pi/S3Gateway/
```

Install/verify the approved `samplelist.csv` and `pygw_conf.py` there, then run:

```bash
sudo s3-gateway-dbup
```

Verify counts:

```bash
sudo -u s3gw psql -d "serial-gateway-program" -c \
"SELECT pan_id, channel, COUNT(*) FROM node_database GROUP BY pan_id, channel ORDER BY pan_id, channel;"
```

---

## 15. Connect the Zigbee USB gateway

Connect the approved CP210x-based Zigbee gateway.

Verify USB detection:

```bash
lsusb | grep -i 'CP210'
ls -l /dev/ttyUSB*
```

The current production architecture operates one active Zigbee USB gateway per running gateway process. Simultaneous dual-channel operation is future development and is outside the handover baseline.

---

## 16. Production validation

Run:

```bash
echo "=== S3 PRODUCTION VALIDATION ==="

sudo systemctl is-enabled s3-zigbee-gateway
sudo systemctl is-active s3-zigbee-gateway
ps -ef | grep '[p]ygw_main.py'
sudo systemctl show s3-zigbee-gateway -p ExecStart

readlink -f /opt/s3-gateway/app/PYSerialGateway/GPSlog
sudo -u s3gw test -w /home/pi/S3Gateway/GPSlog \
  && echo "GPS write PASS" \
  || echo "GPS write FAIL"

sudo visudo -cf /etc/sudoers.d/s3-gateway-hwreset

sudo -u s3gw test -w /opt/s3-gateway/app/pyserialgateway/hardware_reset.py \
  && echo "FAIL reset script writable" \
  || echo "PASS reset script protected"

systemctl is-active s3-gateway-log-maintenance.timer
lsusb | grep -i 'CP210'

tail -n 30 /home/pi/S3Gateway/log/gateway.log
tail -n 30 /home/pi/S3Gateway/log/mqtt.log
```

Target state:

```text
s3-zigbee-gateway enabled
s3-zigbee-gateway active
pygw_main.py GPSUP
GPS path -> /home/pi/S3Gateway/GPSlog
GPS write PASS
sudoers validation PASS
reset script protected
log-maintenance timer active
CP210x detected
MQTT broker connected / transport ready
```

---

## 17. Controlled reboot acceptance

Reboot the completed unit:

```bash
sudo reboot
```

After reconnecting:

```bash
sudo systemctl is-enabled s3-zigbee-gateway
sudo systemctl is-active s3-zigbee-gateway
ps -ef | grep '[p]ygw_main.py'
systemctl is-active s3-gateway-log-maintenance.timer
```

The unit is not ready for handover if the gateway does not recover automatically after reboot.

---

## 18. Production handover package

Production Team must provide the Project Team with:

- completed Raspberry Pi gateway hardware;
- configured Zigbee USB gateway;
- site node inventory loaded;
- site PAN/channel configuration loaded;
- service enabled and running;
- MQTT connectivity validated;
- GPSUP validated;
- log maintenance validated;
- Project Team operator directory available;
- `README-OPERATOR.md` available in `/home/pi/S3Gateway/`;
- source revision/commit recorded on the production build record.

Do **not** hand over production secrets in an unsecured document.

---

## 19. Handover acceptance — Production Team

The Production Team handover is accepted when the technician can independently demonstrate:

- [ ] Image/install the approved Raspberry Pi OS.
- [ ] Configure network/time/SSH according to company deployment policy.
- [ ] Install required OS packages.
- [ ] Create/verify the `s3gw` service account.
- [ ] Install and initialize PostgreSQL for a new unit.
- [ ] Obtain the approved Git source revision.
- [ ] Build the production Python `.venv`.
- [ ] Configure production `.env` without exposing secrets.
- [ ] Install approved site files.
- [ ] Install/enable the base systemd service.
- [ ] Run `deploy-production.sh` successfully.
- [ ] Install/verify log retention.
- [ ] Initialize site nodes with `s3-gateway-dbup`.
- [ ] Detect the Zigbee USB gateway.
- [ ] Validate MQTT and gateway operation.
- [ ] Perform a controlled reboot and confirm automatic recovery.
- [ ] Hand the unit to the Project Team with the operator workspace ready.

---

## Deferred / future development

Do not block handover on these items:

- simultaneous multi-USB/multi-channel operation;
- dedicated multi-instance service template;
- USB-specific hardware reset isolation;
- new set-timetable/set-active-profile APIs;
- application/source-code redesign.
