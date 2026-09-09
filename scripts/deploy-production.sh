#!/bin/bash

set -euo pipefail

SERVICE_NAME="s3-zigbee-gateway"
TARGET_DIR="/opt/s3-gateway/app"
BACKUP_ROOT="/opt/s3-gateway/backups"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this deployment script with sudo/root." >&2
    exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required for deployment." >&2
    exit 1
fi

if [ ! -d "$SOURCE_DIR/PYSerialGateway" ] || [ ! -d "$SOURCE_DIR/pyserialgateway" ]; then
    echo "Repository layout not recognized at: $SOURCE_DIR" >&2
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Production target does not exist: $TARGET_DIR" >&2
    exit 1
fi

if [ ! -f "$TARGET_DIR/.env" ]; then
    echo "Refusing deployment because production .env is missing: $TARGET_DIR/.env" >&2
    exit 1
fi

if [ ! -x "$TARGET_DIR/.venv/bin/python" ]; then
    echo "Refusing deployment because production virtualenv is missing: $TARGET_DIR/.venv" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

restart_service() {
    systemctl start "$SERVICE_NAME" >/dev/null 2>&1 || true
}
trap restart_service EXIT

echo "Stopping $SERVICE_NAME..."
systemctl stop "$SERVICE_NAME"

echo "Backing up deploy-managed files to $BACKUP_DIR..."
rsync -a \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='.venv/' \
    --exclude='PYSerialGateway/samplelist.csv' \
    --exclude='PYSerialGateway/log/' \
    --exclude='PYSerialGateway/errorlog/' \
    --exclude='PYSerialGateway/GPSlog/' \
    --exclude='mqtt_buffer.db' \
    --exclude='*.mqtt.db' \
    "$TARGET_DIR/" "$BACKUP_DIR/"

echo "Deploying code from $SOURCE_DIR to $TARGET_DIR..."
rsync -a --delete \
    --chown=root:s3gw \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='.venv/' \
    --exclude='PYSerialGateway/samplelist.csv' \
    --exclude='PYSerialGateway/log/' \
    --exclude='PYSerialGateway/errorlog/' \
    --exclude='PYSerialGateway/GPSlog/' \
    --exclude='mqtt_buffer.db' \
    --exclude='*.mqtt.db' \
    "$SOURCE_DIR/" "$TARGET_DIR/"

chmod 750 "$TARGET_DIR/PYSerialGateway/run-service.sh"

# Runtime directories remain writable by the service account.
install -d -o s3gw -g s3gw -m 750 \
    "$TARGET_DIR/PYSerialGateway/log" \
    "$TARGET_DIR/PYSerialGateway/errorlog" \
    "$TARGET_DIR/PYSerialGateway/GPSlog"

# Validate the production launcher and critical Python modules without
# executing DB synchronization or starting the gateway manually.
"$TARGET_DIR/.venv/bin/python" -c \
"for p in [
'$TARGET_DIR/pyserialgateway/PYGatewayListener/config.py',
'$TARGET_DIR/pyserialgateway/PYGatewayListener/db_connection.py',
'$TARGET_DIR/pyserialgateway/PYGatewayListener/rest_api.py'
]: compile(open(p).read(), p, 'exec'); print('SYNTAX_PASS', p)"

bash -n "$TARGET_DIR/PYSerialGateway/run-service.sh"

echo "Starting $SERVICE_NAME..."
systemctl start "$SERVICE_NAME"
trap - EXIT

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Deployment completed but service is not active." >&2
    echo "Backup available at: $BACKUP_DIR" >&2
    exit 1
fi

echo "Deployment complete."
echo "Backup: $BACKUP_DIR"
systemctl --no-pager --full status "$SERVICE_NAME" | sed -n '1,12p'
