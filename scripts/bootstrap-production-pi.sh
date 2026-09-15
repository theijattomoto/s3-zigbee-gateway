#!/bin/bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-s3-zigbee-gateway}"
TARGET_DIR="${TARGET_DIR:-/opt/s3-gateway/app}"
OPERATOR_DIR="${S3_OPERATOR_DIR:-/home/pi/S3Gateway}"
DB_NAME="${DB_NAME:-serial-gateway-program}"
SERVICE_USER="${SERVICE_USER:-s3gw}"
SERVICE_GROUP="${SERVICE_GROUP:-s3gw}"
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BASE_UNIT="$SOURCE_DIR/deploy/systemd/s3-zigbee-gateway.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo/root." >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This bootstrap currently supports Raspberry Pi OS/Debian systems with apt-get." >&2
    exit 1
fi

if [ ! -f "$SOURCE_DIR/requirements.txt" ] || [ ! -f "$BASE_UNIT" ]; then
    echo "Repository layout not recognized at $SOURCE_DIR" >&2
    exit 1
fi

if [ -d "$TARGET_DIR" ] && [ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
    echo "Refusing fresh bootstrap because target is not empty: $TARGET_DIR" >&2
    echo "Use deploy-production.sh for an existing gateway." >&2
    exit 1
fi

echo "Installing required OS packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
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

for cmd in install rsync setfacl psql runuser systemctl python3; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "Required command unavailable after package installation: $cmd" >&2
        exit 1
    }
done

if id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "Service account exists: $SERVICE_USER"
else
    useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "Created service account: $SERVICE_USER"
fi

if getent group dialout >/dev/null 2>&1; then
    usermod -a -G dialout "$SERVICE_USER"
else
    echo "Required serial-access group 'dialout' is missing." >&2
    exit 1
fi

if ! id -nG "$SERVICE_USER" | tr ' ' '\n' | grep -qx dialout; then
    echo "$SERVICE_USER was not added to dialout successfully." >&2
    exit 1
fi

systemctl enable --now postgresql

if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${SERVICE_USER}'" | grep -q '^1$'; then
    runuser -u postgres -- createuser "$SERVICE_USER"
fi

if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q '^1$'; then
    echo "Database already exists: $DB_NAME"
else
    runuser -u postgres -- createdb -O "$SERVICE_USER" "$DB_NAME"
fi

if ! runuser -u postgres -- psql -d "$DB_NAME" -tAc "SELECT to_regclass('public.node_database') IS NOT NULL" | grep -q '^t$'; then
    runuser -u postgres -- psql -d "$DB_NAME" <<SQL
CREATE TABLE node_database (
    id SERIAL PRIMARY KEY,
    pole_node TEXT,
    node TEXT NOT NULL,
    pan_id TEXT,
    channel TEXT,
    latitude TEXT,
    longitude TEXT,
    description TEXT
);
CREATE INDEX idx_node_database_node ON node_database (node);
CREATE INDEX idx_node_database_pan_channel ON node_database (pan_id, channel);

CREATE TABLE filter_time_py (
    id SERIAL PRIMARY KEY,
    node TEXT NOT NULL,
    ack TEXT NOT NULL,
    dtime TIMESTAMP,
    msgid TEXT,
    oo_msgid TEXT,
    dec_count INTEGER DEFAULT 0,
    rollover_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    override_flag BOOLEAN,
    lamp_status BOOLEAN
);
CREATE INDEX idx_filter_time_py_node_ack ON filter_time_py (node, ack);

ALTER TABLE node_database OWNER TO ${SERVICE_USER};
ALTER TABLE filter_time_py OWNER TO ${SERVICE_USER};
ALTER SEQUENCE node_database_id_seq OWNER TO ${SERVICE_USER};
ALTER SEQUENCE filter_time_py_id_seq OWNER TO ${SERVICE_USER};
SQL
fi

install -d -o root -g "$SERVICE_GROUP" -m 755 /opt/s3-gateway
install -d -o root -g "$SERVICE_GROUP" -m 755 "$TARGET_DIR"
install -d -o root -g root -m 755 /opt/s3-gateway/backups

rsync -a --delete --exclude=.git/ "$SOURCE_DIR/" "$TARGET_DIR/"
chown -R root:"$SERVICE_GROUP" "$TARGET_DIR"

python3 -m venv "$TARGET_DIR/.venv"
"$TARGET_DIR/.venv/bin/pip" install --upgrade pip
"$TARGET_DIR/.venv/bin/pip" install -r "$TARGET_DIR/requirements.txt"

if [ ! -f "$TARGET_DIR/.env" ]; then
    cp "$TARGET_DIR/.env.example" "$TARGET_DIR/.env"
fi
sed -i "s/^DB_USER=.*/DB_USER=${SERVICE_USER}/" "$TARGET_DIR/.env"
chown root:"$SERVICE_GROUP" "$TARGET_DIR/.env"
chmod 640 "$TARGET_DIR/.env"

if ! id pi >/dev/null 2>&1; then
    echo "Required operator account 'pi' does not exist. Create the approved operator account before continuing." >&2
    exit 1
fi

install -d -o pi -g pi -m 755 "$OPERATOR_DIR"
if [ ! -f "$OPERATOR_DIR/samplelist.csv" ]; then
    install -o pi -g pi -m 644 "$TARGET_DIR/PYSerialGateway/samplelist.csv" "$OPERATOR_DIR/samplelist.csv"
fi
if [ ! -f "$OPERATOR_DIR/pygw_conf.py" ]; then
    install -o pi -g pi -m 644 "$TARGET_DIR/PYSerialGateway/pygw_conf.py" "$OPERATOR_DIR/pygw_conf.py"
fi

install -o root -g root -m 644 "$BASE_UNIT" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

cat <<EOF
Fresh-Pi bootstrap preparation complete.

NEXT REQUIRED STEPS:
1. Edit production secrets/settings:
   $TARGET_DIR/.env
2. Replace site files if required:
   $OPERATOR_DIR/samplelist.csv
   $OPERATOR_DIR/pygw_conf.py
3. Confirm required encrypted required-<site>gw.zip bundle exists.
4. Run:
   cd $SOURCE_DIR
   sudo ./scripts/deploy-production.sh
   sudo bash scripts/install-log-retention.sh
   sudo s3-gateway-dbup
   sudo bash scripts/validate-handover.sh

The gateway service is enabled but production acceptance is not complete until validation passes.
EOF
