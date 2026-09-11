#!/bin/bash

set -euo pipefail

LOG_DIR="${GATEWAY_LOG_DIR:-/home/pi/S3Gateway/log}"

if [ ! -d "$LOG_DIR" ]; then
    exit 0
fi

# Compress rotated gateway logs after they have remained plain for 7 days.
find "$LOG_DIR" -type f \
    \( -name 'gateway.log.*' -o -name 'error.log.*' -o -name 'mqtt.log.*' \) \
    ! -name '*.gz' \
    -mtime +7 \
    -exec gzip -- {} \;

# Remove archived logs older than 90 days.
find "$LOG_DIR" -type f \
    \( -name 'gateway.log.*.gz' -o -name 'error.log.*.gz' -o -name 'mqtt.log.*.gz' \) \
    -mtime +90 \
    -delete
