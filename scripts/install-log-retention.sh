#!/bin/bash

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo/root." >&2
    exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
OPERATOR_CONFIG="${S3_OPERATOR_CONFIG:-/etc/s3-gateway/operator.conf}"
if [ -f "$OPERATOR_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$OPERATOR_CONFIG"
fi
OPERATOR_USER="${S3_OPERATOR_USER:-${SUDO_USER:-pi}}"
if [ "$OPERATOR_USER" = "root" ]; then OPERATOR_USER="pi"; fi
OPERATOR_GROUP="${S3_OPERATOR_GROUP:-$(id -gn "$OPERATOR_USER" 2>/dev/null || echo "$OPERATOR_USER")}"
OPERATOR_HOME="${S3_OPERATOR_HOME:-$(getent passwd "$OPERATOR_USER" | cut -d: -f6)}"
OPERATOR_DIR="${S3_OPERATOR_DIR:-$OPERATOR_HOME/S3Gateway}"
LOG_DIR="$OPERATOR_DIR/log"

id "$OPERATOR_USER" >/dev/null 2>&1 || { echo "Operator user missing: $OPERATOR_USER" >&2; exit 1; }
[ -n "$OPERATOR_HOME" ] && [ -d "$OPERATOR_HOME" ] || { echo "Operator home unavailable: $OPERATOR_HOME" >&2; exit 1; }

install -o root -g root -m 755 \
    "$SOURCE_DIR/scripts/log-maintenance.sh" \
    /usr/local/sbin/s3-gateway-log-maintenance

cat > /etc/logrotate.d/s3-gateway <<EOF
$LOG_DIR/gateway.log
$LOG_DIR/error.log
$LOG_DIR/mqtt.log {
    daily
    missingok
    notifempty
    rotate 365
    dateext
    dateformat .%Y-%m-%d
    nocompress
    copytruncate
    su $OPERATOR_USER s3gw
}
EOF
chmod 644 /etc/logrotate.d/s3-gateway

cat > /etc/systemd/system/s3-gateway-log-maintenance.service <<EOF
[Unit]
Description=S3 Gateway log retention maintenance

[Service]
Type=oneshot
Environment=GATEWAY_LOG_DIR=$LOG_DIR
Environment=S3_OPERATOR_CONFIG=$OPERATOR_CONFIG
ExecStart=/usr/local/sbin/s3-gateway-log-maintenance
EOF
chmod 644 /etc/systemd/system/s3-gateway-log-maintenance.service

install -o root -g root -m 644 \
    "$SOURCE_DIR/deploy/systemd/s3-gateway-log-maintenance.timer" \
    /etc/systemd/system/s3-gateway-log-maintenance.timer

systemd-analyze verify \
    /etc/systemd/system/s3-gateway-log-maintenance.service \
    /etc/systemd/system/s3-gateway-log-maintenance.timer

logrotate -d /etc/logrotate.d/s3-gateway >/dev/null

systemctl daemon-reload
systemctl enable --now s3-gateway-log-maintenance.timer

echo "S3 Gateway log retention installed."
echo "Operator: $OPERATOR_USER"
echo "Log path: $LOG_DIR"
systemctl --no-pager --full status s3-gateway-log-maintenance.timer | sed -n '1,12p'
