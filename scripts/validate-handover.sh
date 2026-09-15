#!/bin/bash
set -u

SERVICE_NAME="${SERVICE_NAME:-s3-zigbee-gateway}"
APP_DIR="${APP_DIR:-/opt/s3-gateway/app}"
OPERATOR_DIR="${S3_OPERATOR_DIR:-/home/pi/S3Gateway}"
DB_NAME="${DB_NAME:-serial-gateway-program}"
MAINT_TIMER="${MAINT_TIMER:-s3-gateway-log-maintenance.timer}"
SUDOERS_FILE="${SUDOERS_FILE:-/etc/sudoers.d/s3-gateway-hwreset}"

PASS=0
WARN=0
FAIL=0

pass() {
    printf 'PASS  %s\n' "$1"
    PASS=$((PASS + 1))
}

warn() {
    printf 'WARN  %s\n' "$1"
    WARN=$((WARN + 1))
}

fail() {
    printf 'FAIL  %s\n' "$1"
    FAIL=$((FAIL + 1))
}

section() {
    printf '\n=== %s ===\n' "$1"
}

section "Service"
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    pass "$SERVICE_NAME enabled"
else
    fail "$SERVICE_NAME not enabled"
fi

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    pass "$SERVICE_NAME active"
else
    fail "$SERVICE_NAME not active"
fi

if ps -eo user,args | grep -F "pygw_main.py GPSUP" | grep -q '^s3gw '; then
    pass "gateway process runs as s3gw with GPSUP"
else
    fail "expected s3gw pygw_main.py GPSUP process not found"
fi

resolved_exec="$(systemctl show "$SERVICE_NAME" -p ExecStart --value 2>/dev/null || true)"
case "$resolved_exec" in
    *"run-service.sh GPSUP"*) pass "effective systemd ExecStart includes GPSUP" ;;
    *) fail "effective systemd ExecStart does not include GPSUP" ;;
esac

section "Operator workspace"
for path in \
    "$OPERATOR_DIR/samplelist.csv" \
    "$OPERATOR_DIR/pygw_conf.py" \
    "$OPERATOR_DIR/README-OPERATOR.md" \
    "$OPERATOR_DIR/log" \
    "$OPERATOR_DIR/GPSlog"
do
    if [ -e "$path" ]; then
        pass "present: $path"
    else
        fail "missing: $path"
    fi
done

expected_gps="$(readlink -f "$OPERATOR_DIR/GPSlog" 2>/dev/null || true)"
runtime_gps="$(readlink -f "$APP_DIR/PYSerialGateway/GPSlog" 2>/dev/null || true)"
if [ -n "$expected_gps" ] && [ "$runtime_gps" = "$expected_gps" ]; then
    pass "runtime GPS path resolves to operator workspace"
else
    fail "runtime GPS path does not resolve to operator workspace"
fi

if runuser -u s3gw -- test -w "$OPERATOR_DIR/GPSlog" 2>/dev/null; then
    pass "s3gw can write GPS operator directory"
else
    fail "s3gw cannot write GPS operator directory"
fi

for log_file in gateway.log mqtt.log error.log; do
    if runuser -u s3gw -- test -w "$OPERATOR_DIR/log/$log_file" 2>/dev/null; then
        pass "s3gw can write $log_file"
    else
        fail "s3gw cannot write $log_file"
    fi
done

section "Runtime protection"
for path in \
    "$APP_DIR" \
    "$APP_DIR/pyserialgateway" \
    "$APP_DIR/pyserialgateway/hardware_reset.py" \
    "$APP_DIR/pyserialgateway/config_PYproperties.py"
do
    if runuser -u s3gw -- test -w "$path" 2>/dev/null; then
        fail "protected path writable by s3gw: $path"
    else
        pass "protected from s3gw write: $path"
    fi
done

if [ -f "$SUDOERS_FILE" ]; then
    if visudo -cf "$SUDOERS_FILE" >/dev/null 2>&1; then
        pass "restricted hardware-reset sudoers file valid"
    else
        fail "hardware-reset sudoers file invalid"
    fi
else
    fail "hardware-reset sudoers file missing"
fi

if runuser -u s3gw -- sudo -n -l 2>/dev/null | grep -Fq "/usr/bin/python3 $APP_DIR/pyserialgateway/hardware_reset.py"; then
    pass "s3gw has approved hardware-reset sudo permission"
else
    fail "approved hardware-reset sudo permission not found"
fi

if runuser -u s3gw -- sudo -n -l 2>/dev/null | grep -Fq 'NOPASSWD: ALL'; then
    fail "s3gw has unsafe NOPASSWD: ALL permission"
else
    pass "no NOPASSWD: ALL permission detected for s3gw"
fi

section "Database"
if runuser -u s3gw -- psql -d "$DB_NAME" -tAc 'select 1' 2>/dev/null | grep -q '^1$'; then
    pass "s3gw PostgreSQL connection"
else
    fail "s3gw cannot connect to PostgreSQL database $DB_NAME"
fi

if runuser -u s3gw -- psql -d "$DB_NAME" -tAc "select to_regclass('public.node_database') is not null and to_regclass('public.filter_time_py') is not null" 2>/dev/null | grep -q '^t$'; then
    pass "required PostgreSQL tables exist"
else
    fail "required PostgreSQL tables missing"
fi

node_count="$(runuser -u s3gw -- psql -d "$DB_NAME" -tAc 'select count(*) from node_database' 2>/dev/null | tr -d '[:space:]' || true)"
if [ -n "$node_count" ] && [ "$node_count" -gt 0 ] 2>/dev/null; then
    pass "node database contains $node_count rows"
else
    fail "node database is empty or unreadable"
fi

section "Maintenance"
if systemctl is-enabled --quiet "$MAINT_TIMER" 2>/dev/null; then
    pass "$MAINT_TIMER enabled"
else
    warn "$MAINT_TIMER not enabled"
fi

if systemctl is-active --quiet "$MAINT_TIMER" 2>/dev/null; then
    pass "$MAINT_TIMER active"
else
    fail "$MAINT_TIMER not active"
fi

section "USB Zigbee"
cp210_count="$(lsusb 2>/dev/null | grep -ic 'CP210' || true)"
if [ "$cp210_count" -ge 1 ] 2>/dev/null; then
    pass "$cp210_count CP210x USB device(s) detected"
else
    fail "no CP210x USB device detected"
fi

if compgen -G '/dev/ttyUSB*' >/dev/null; then
    pass "ttyUSB serial device present"
else
    fail "no /dev/ttyUSB* serial device present"
fi

section "MQTT evidence"
MQTT_LOG="$OPERATOR_DIR/log/mqtt.log"
if [ -f "$MQTT_LOG" ]; then
    if tail -n 500 "$MQTT_LOG" | grep -Fq 'MQTT transport ready'; then
        pass "MQTT transport-ready evidence found"
    else
        warn "no recent MQTT transport-ready evidence found"
    fi
    if tail -n 500 "$MQTT_LOG" | grep -Fq 'MQTT broker connected'; then
        pass "MQTT broker-connected evidence found"
    else
        warn "no recent MQTT broker-connected evidence found"
    fi
else
    fail "MQTT log missing"
fi

section "Summary"
printf 'PASS=%d WARN=%d FAIL=%d\n' "$PASS" "$WARN" "$FAIL"

if [ "$FAIL" -gt 0 ]; then
    echo "HANDOVER RESULT: FAIL"
    exit 1
fi

if [ "$WARN" -gt 0 ]; then
    echo "HANDOVER RESULT: PASS WITH WARNINGS"
    exit 0
fi

echo "HANDOVER RESULT: PASS"
