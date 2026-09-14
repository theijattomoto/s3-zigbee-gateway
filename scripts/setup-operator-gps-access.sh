#!/bin/bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/s3-gateway/app}"
OPERATOR_DIR="${OPERATOR_DIR:-/home/pi/S3Gateway}"
RUNTIME_GPS_DIR="$TARGET_DIR/PYSerialGateway/GPSlog"
OPERATOR_GPS_DIR="$OPERATOR_DIR/GPSlog"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/s3-gateway/backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/operator-gps-$TIMESTAMP"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo/root." >&2
    exit 1
fi

command -v rsync >/dev/null 2>&1 || { echo "rsync is required." >&2; exit 1; }
command -v setfacl >/dev/null 2>&1 || { echo "setfacl is required." >&2; exit 1; }

install -d -o pi -g s3gw -m 2775 "$OPERATOR_GPS_DIR"
setfacl -m u:s3gw:rwx "$OPERATOR_GPS_DIR"
setfacl -m u:pi:rwx "$OPERATOR_GPS_DIR"
setfacl -d -m u:s3gw:rwx "$OPERATOR_GPS_DIR"
setfacl -d -m u:pi:rwX "$OPERATOR_GPS_DIR"
setfacl -d -m m:rwx "$OPERATOR_GPS_DIR"
setfacl -m u:s3gw:x /home/pi
setfacl -m u:s3gw:x "$OPERATOR_DIR"

if [ -L "$RUNTIME_GPS_DIR" ]; then
    current_target="$(readlink -f "$RUNTIME_GPS_DIR")"
    expected_target="$(readlink -f "$OPERATOR_GPS_DIR")"
    if [ "$current_target" = "$expected_target" ]; then
        echo "GPS operator access already configured: $RUNTIME_GPS_DIR -> $OPERATOR_GPS_DIR"
        exit 0
    fi
    echo "Refusing to replace unexpected GPSlog symlink: $RUNTIME_GPS_DIR -> $current_target" >&2
    exit 1
fi

if [ -d "$RUNTIME_GPS_DIR" ]; then
    install -d -m 750 "$BACKUP_DIR/GPSlog-legacy"
    rsync -a "$RUNTIME_GPS_DIR/" "$BACKUP_DIR/GPSlog-legacy/"
    rsync -a --ignore-existing "$RUNTIME_GPS_DIR/" "$OPERATOR_GPS_DIR/"
    rm -rf "$RUNTIME_GPS_DIR"
fi

ln -s "$OPERATOR_GPS_DIR" "$RUNTIME_GPS_DIR"
chown -h root:s3gw "$RUNTIME_GPS_DIR"

if ! runuser -u s3gw -- test -w "$OPERATOR_GPS_DIR"; then
    echo "s3gw cannot write to $OPERATOR_GPS_DIR" >&2
    exit 1
fi

if [ "$(readlink -f "$RUNTIME_GPS_DIR")" != "$(readlink -f "$OPERATOR_GPS_DIR")" ]; then
    echo "GPSlog symlink verification failed." >&2
    exit 1
fi

echo "Operator GPS access configured."
echo "Runtime path : $RUNTIME_GPS_DIR"
echo "Operator path: $OPERATOR_GPS_DIR"
echo "Backup      : $BACKUP_DIR"
