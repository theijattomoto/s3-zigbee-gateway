#!/bin/bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/s3-gateway/app}"
OPERATOR_CONFIG="${S3_OPERATOR_CONFIG:-/etc/s3-gateway/operator.conf}"
if [ -f "$OPERATOR_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$OPERATOR_CONFIG"
fi
OPERATOR_USER="${OPERATOR_USER:-${S3_OPERATOR_USER:-${SUDO_USER:-pi}}}"
if [ "$OPERATOR_USER" = "root" ]; then OPERATOR_USER="pi"; fi
OPERATOR_GROUP="${OPERATOR_GROUP:-${S3_OPERATOR_GROUP:-$(id -gn "$OPERATOR_USER")}}"
OPERATOR_HOME="${OPERATOR_HOME:-${S3_OPERATOR_HOME:-$(getent passwd "$OPERATOR_USER" | cut -d: -f6)}}"
OPERATOR_DIR="${OPERATOR_DIR:-${S3_OPERATOR_DIR:-$OPERATOR_HOME/S3Gateway}}"
RUNTIME_GPS_DIR="$TARGET_DIR/PYSerialGateway/GPSlog"
OPERATOR_GPS_DIR="$OPERATOR_DIR/GPSlog"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/s3-gateway/backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/operator-gps-$TIMESTAMP"

if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo/root." >&2; exit 1; fi
command -v rsync >/dev/null 2>&1 || { echo "rsync is required." >&2; exit 1; }
command -v setfacl >/dev/null 2>&1 || { echo "setfacl is required." >&2; exit 1; }
id "$OPERATOR_USER" >/dev/null 2>&1 || { echo "Operator user missing: $OPERATOR_USER" >&2; exit 1; }

apply_operator_gps_permissions() {
    install -d -o "$OPERATOR_USER" -g s3gw -m 2775 "$OPERATOR_GPS_DIR"
    setfacl -m u:s3gw:rwx "$OPERATOR_GPS_DIR"
    setfacl -m u:"$OPERATOR_USER":rwx "$OPERATOR_GPS_DIR"
    setfacl -d -m u:s3gw:rwx "$OPERATOR_GPS_DIR"
    setfacl -d -m u:"$OPERATOR_USER":rwX "$OPERATOR_GPS_DIR"
    setfacl -d -m m:rwx "$OPERATOR_GPS_DIR"
    setfacl -m u:s3gw:x "$OPERATOR_HOME"
    setfacl -m u:s3gw:x "$OPERATOR_DIR"
}

verify_operator_gps_access() {
    runuser -u s3gw -- test -w "$OPERATOR_GPS_DIR" || { echo "s3gw cannot write to $OPERATOR_GPS_DIR" >&2; exit 1; }
    [ "$(readlink -f "$RUNTIME_GPS_DIR")" = "$(readlink -f "$OPERATOR_GPS_DIR")" ] || { echo "GPSlog symlink verification failed." >&2; exit 1; }
}

apply_operator_gps_permissions

if [ -L "$RUNTIME_GPS_DIR" ]; then
    current_target="$(readlink -f "$RUNTIME_GPS_DIR")"
    expected_target="$(readlink -f "$OPERATOR_GPS_DIR")"
    [ "$current_target" = "$expected_target" ] || { echo "Refusing to replace unexpected GPSlog symlink: $RUNTIME_GPS_DIR -> $current_target" >&2; exit 1; }
    verify_operator_gps_access
    echo "GPS operator access already configured: $RUNTIME_GPS_DIR -> $OPERATOR_GPS_DIR"
    exit 0
fi

if [ -e "$RUNTIME_GPS_DIR" ] && [ ! -d "$RUNTIME_GPS_DIR" ]; then echo "Refusing to replace unexpected non-directory GPSlog path: $RUNTIME_GPS_DIR" >&2; exit 1; fi

if [ -d "$RUNTIME_GPS_DIR" ]; then
    install -d -m 750 "$BACKUP_DIR/GPSlog-legacy"
    rsync -a "$RUNTIME_GPS_DIR/" "$BACKUP_DIR/GPSlog-legacy/"
    rsync -a --ignore-existing "$RUNTIME_GPS_DIR/" "$OPERATOR_GPS_DIR/"
    rm -rf "$RUNTIME_GPS_DIR"
fi

apply_operator_gps_permissions
ln -s "$OPERATOR_GPS_DIR" "$RUNTIME_GPS_DIR"
chown -h root:s3gw "$RUNTIME_GPS_DIR"
verify_operator_gps_access

echo "Operator GPS access configured."
echo "Operator     : $OPERATOR_USER"
echo "Runtime path : $RUNTIME_GPS_DIR"
echo "Operator path: $OPERATOR_GPS_DIR"
if [ -d "$BACKUP_DIR/GPSlog-legacy" ]; then echo "Backup       : $BACKUP_DIR"; else echo "Backup       : not required"; fi
