#!/usr/bin/env python3
"""Synchronize the operator CSV into PostgreSQL without touching Zigbee serial.

This helper is intentionally separate from the long-running gateway launcher.
Production DBUP must be deterministic even when the Zigbee USB adapter is
missing, on the wrong RF configuration, or not responding to +DS.
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "PYSerialGateway" / "pygw_main.py"

# config.py derives the operator CSV path from sys.argv[0], matching the legacy
# gateway launcher's behavior. Point it at the production launcher before the
# gateway modules are imported.
sys.path.insert(0, str(REPO_ROOT))
sys.argv[0] = str(LAUNCHER)

from pyserialgateway.PYGatewayListener.config import (  # noqa: E402
    first_GW_data,
    second_GW_data,
    updating_database_localpath,
)
from pyserialgateway.PYGatewayListener.database_aligner import DatabaseAligner  # noqa: E402
from pyserialgateway.PYGatewayListener.db_connection import get_connection  # noqa: E402


def _load_expected_rows(csv_path: Path) -> dict[str, tuple[str, str, str, str]]:
    required = ["pole_node", "node", "pan_id", "channel"]
    expected: dict[str, tuple[str, str, str, str]] = {}

    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != required:
            raise RuntimeError(
                "CSV header must be exactly: " + ",".join(required)
            )

        for line_no, row in enumerate(reader, start=2):
            values = tuple((row.get(key) or "").strip() for key in required)
            if not any(values):
                continue
            if not all(values):
                raise RuntimeError(f"Incomplete CSV row at line {line_no}")
            pole_node, node, pan_id, channel = values
            if node in expected:
                raise RuntimeError(f"Duplicate node ID {node} at line {line_no}")
            expected[node] = (pole_node, node, pan_id, channel)

    if not expected:
        raise RuntimeError("CSV contains no target nodes")

    return expected


def _verify_database(
    expected_targets: dict[str, tuple[str, str, str, str]],
) -> int:
    expected = dict(expected_targets)
    expected[first_GW_data[0]] = ("GW-1",) + tuple(first_GW_data)
    expected[second_GW_data[0]] = ("GW-2",) + tuple(second_GW_data)

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pole_node, node, pan_id, channel "
                "FROM node_database ORDER BY node"
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    actual: dict[str, tuple[str, str, str, str]] = {}
    duplicate_nodes: list[str] = []
    for row in rows:
        normalized = tuple("" if value is None else str(value) for value in row)
        node = normalized[1]
        if node in actual:
            duplicate_nodes.append(node)
        actual[node] = normalized

    if duplicate_nodes:
        raise RuntimeError(
            "Duplicate node rows remain in PostgreSQL: "
            + ", ".join(sorted(set(duplicate_nodes)))
        )

    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        mismatched = sorted(
            node
            for node in set(expected) & set(actual)
            if expected[node] != actual[node]
        )
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        if mismatched:
            details.append("mismatched=" + ",".join(mismatched))
        raise RuntimeError(
            "PostgreSQL node_database does not match operator CSV/GW config"
            + (": " + "; ".join(details) if details else "")
        )

    return len(rows)


def main() -> int:
    logger = logging.getLogger("s3-dbup")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers[:] = [handler]
    logger.propagate = False

    csv_path = Path(updating_database_localpath)
    expected_targets = _load_expected_rows(csv_path)

    logger.info("DBUP serial-independent synchronization starting")
    logger.info("Operator CSV: %s", csv_path)
    logger.info("Target nodes: %d", len(expected_targets))

    aligner = DatabaseAligner()
    aligner.run(
        logger,
        logger,
        logger,
        first_GW_data,
        [first_GW_data, second_GW_data],
        True,
    )

    row_count = _verify_database(expected_targets)
    logger.info("DBUP sync verification: PASS")
    logger.info("PostgreSQL node_database rows: %d", row_count)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("DBUP interrupted by operator.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"DBUP ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
