#!/bin/bash

set -e

REPO_DIR="/home/pi/gateway-test/s3-zigbee-gateway"
APP_DIR="$REPO_DIR/PYSerialGateway"
PYTHON="$REPO_DIR/.venv/bin/python"

echo "Starting S3 Serial Gateway"

cd "$APP_DIR"
exec "$PYTHON" pygw_main.py "$@"
