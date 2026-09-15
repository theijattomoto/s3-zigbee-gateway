#!/bin/bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/opt/s3-gateway/app}"
SERVICE_NAME="${SERVICE_NAME:-s3-zigbee-gateway}"
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DROPIN_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
DROPIN_FILE="$DROPIN_DIR/override.conf"
SUDOERS_FILE="/etc/sudoers.d/s3-gateway-hwreset"
RESET_SCRIPT="$TARGET_DIR/pyserialgateway/hardware_reset.py"
RESET_CONFIG="$TARGET_DIR/pyserialgateway/config_PYproperties.py"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo/root." >&2
    exit 1
fi

command -v visudo >/dev/null 2>&1 || { echo "visudo is required." >&2; exit 1; }
command -v runuser >/dev/null 2>&1 || { echo "runuser is required." >&2; exit 1; }

install -d -o root -g root -m 755 "$DROPIN_DIR"
install -o root -g root -m 644 \
    "$SOURCE_DIR/deploy/systemd/s3-zigbee-gateway-gpsup.conf" \
    "$DROPIN_FILE"

install -o root -g root -m 440 \
    "$SOURCE_DIR/deploy/sudoers/s3-gateway-hwreset" \
    "$SUDOERS_FILE"

visudo -cf "$SUDOERS_FILE"

# Protect the privileged code path. The normal gateway runtime remains under
# PYSerialGateway and is intentionally left writable where required.
chown root:root "$TARGET_DIR" "$TARGET_DIR/pyserialgateway"
chmod 755 "$TARGET_DIR" "$TARGET_DIR/pyserialgateway"
chown root:root "$RESET_SCRIPT" "$RESET_CONFIG"
chmod 644 "$RESET_SCRIPT" "$RESET_CONFIG"
rm -rf "$TARGET_DIR/pyserialgateway/__pycache__"

if runuser -u s3gw -- test -w "$TARGET_DIR"; then
    echo "Refusing to continue: s3gw can write to $TARGET_DIR" >&2
    exit 1
fi
if runuser -u s3gw -- test -w "$TARGET_DIR/pyserialgateway"; then
    echo "Refusing to continue: s3gw can write to $TARGET_DIR/pyserialgateway" >&2
    exit 1
fi
if runuser -u s3gw -- test -w "$RESET_SCRIPT"; then
    echo "Refusing to continue: s3gw can modify $RESET_SCRIPT" >&2
    exit 1
fi
if runuser -u s3gw -- test -w "$RESET_CONFIG"; then
    echo "Refusing to continue: s3gw can modify $RESET_CONFIG" >&2
    exit 1
fi

systemctl daemon-reload

resolved_exec="$(systemctl show "$SERVICE_NAME" -p ExecStart --value)"
case "$resolved_exec" in
    *"run-service.sh GPSUP"*) ;;
    *)
        echo "GPSUP systemd override is not effective: $resolved_exec" >&2
        exit 1
        ;;
esac

if ! runuser -u s3gw -- sudo -n -l | grep -Fq "/usr/bin/python3 $RESET_SCRIPT"; then
    echo "Restricted hardware-reset sudo permission is not effective." >&2
    exit 1
fi

echo "Runtime hardening configured."
echo "GPSUP override : $DROPIN_FILE"
echo "HW reset sudo  : $SUDOERS_FILE"
echo "Privileged code: protected"
