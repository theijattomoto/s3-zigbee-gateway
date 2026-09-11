#!/bin/bash

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer with sudo/root." >&2
    exit 1
fi

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

install -o root -g root -m 755 \
    "$SOURCE_DIR/scripts/log-maintenance.sh" \
    /usr/local/sbin/s3-gateway-log-maintenance

install -o root -g root -m 644 \
    "$SOURCE_DIR/deploy/logrotate/s3-gateway" \
    /etc/logrotate.d/s3-gateway

install -o root -g root -m 644 \
    "$SOURCE_DIR/deploy/systemd/s3-gateway-log-maintenance.service" \
    /etc/systemd/system/s3-gateway-log-maintenance.service

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
systemctl --no-pager --full status s3-gateway-log-maintenance.timer | sed -n '1,12p'
