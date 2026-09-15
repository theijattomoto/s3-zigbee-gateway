#!/bin/bash

set -euo pipefail

OPERATOR_CONFIG="${S3_OPERATOR_CONFIG:-/etc/s3-gateway/operator.conf}"
if [ -f "$OPERATOR_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$OPERATOR_CONFIG"
fi

OPERATOR_USER="${S3_OPERATOR_USER:-pi}"
OPERATOR_HOME="${S3_OPERATOR_HOME:-$(getent passwd "$OPERATOR_USER" 2>/dev/null | cut -d: -f6)}"
OPERATOR_DIR="${S3_OPERATOR_DIR:-${OPERATOR_HOME:-/home/pi}/S3Gateway}"
LOG_DIR="${GATEWAY_LOG_DIR:-$OPERATOR_DIR/log}"

if [ ! -d "$LOG_DIR" ]; then
    exit 0
fi

find "$LOG_DIR" -type f \
    \( -name 'gateway.log.*' -o -name 'error.log.*' -o -name 'mqtt.log.*' \) \
    ! -name '*.gz' \
    -mtime +7 \
    -exec gzip -- {} \;

find "$LOG_DIR" -type f \
    \( -name 'gateway.log.*.gz' -o -name 'error.log.*.gz' -o -name 'mqtt.log.*.gz' \) \
    -mtime +90 \
    -delete
