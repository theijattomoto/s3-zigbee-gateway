#!/bin/bash

set -e

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$SCRIPT_DIR"
PYTHON="$REPO_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Gateway Python runtime not found or not executable: $PYTHON" >&2
    exit 1
fi

echo "Starting S3 Serial Gateway"

cd "$APP_DIR"
exec "$PYTHON" pygw_main.py "$@"
