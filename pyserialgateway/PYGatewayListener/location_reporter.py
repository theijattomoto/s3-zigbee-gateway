"""Automatic one-time S3 node location reporting.

The legacy GPS pipeline remains authoritative for acquiring and confirming a
node fix. This module only reads confirmed coordinates already stored in
PostgreSQL and reports each node location once to MQTT.

Delivery state is persisted separately from the legacy node_database so DBUP
and existing gateway behaviour remain unchanged.
"""

from datetime import datetime, timezone
import logging
import math
import os
import re
import sqlite3
import threading
from contextlib import closing
from typing import Callable, Iterable, Optional

from .db_connection import get_connection
from ..mqtt_service.config import MQTTConfig
from ..mqtt_service.mirroring import publish_confirmed_location


_LOG = logging.getLogger("S3LocationReporter")
_NODE_RE = re.compile(r"^[0-9A-Fa-f]{4}$")
_REFERENCE_COORDINATE = (3.069900, 101.692244)


def _default_state_db() -> str:
    configured = os.getenv("S3_LOCATION_STATE_DB")
    if configured:
        return configured

    mqtt_buffer = MQTTConfig.from_env().buffer_db
    directory = os.path.dirname(os.path.abspath(mqtt_buffer))
    return os.path.join(directory, "location_report_state.db")


def _valid_coordinate(latitude, longitude, description=None) -> bool:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False

    if not math.isfinite(lat) or not math.isfinite(lon):
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    if lat == 0.0 and lon == 0.0:
        return False

    if abs(lat - _REFERENCE_COORDINATE[0]) < 1e-9 and abs(
        lon - _REFERENCE_COORDINATE[1]
    ) < 1e-9:
        return False

    if str(description or "").strip() == "#G0!":
        return False

    return True


def _fetch_location_rows() -> Iterable[dict]:
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT node, pole_node, latitude, longitude, description
            FROM node_database
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY node
            """
        )
        return [
            {
                "node_id": row[0],
                "pole_node": row[1],
                "latitude": row[2],
                "longitude": row[3],
                "description": row[4],
            }
            for row in cursor.fetchall()
        ]
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


class S3LocationReporter(threading.Thread):
    """Periodically reports unreported valid node locations.

    A node is marked reported only after the MQTT QoS 1 publish has completed.
    The unique key is (gateway_id, node_id), intentionally making location a
    one-time installation fact for this phase.
    """

    def __init__(
        self,
        gateway_id: str,
        state_db: Optional[str] = None,
        scan_interval_seconds: Optional[float] = None,
        fetch_rows: Callable[[], Iterable[dict]] = _fetch_location_rows,
        publisher: Callable[[str, dict], bool] = publish_confirmed_location,
    ):
        super().__init__(name="S3LocationReporter", daemon=True)
        self.gateway_id = str(gateway_id or "").strip()
        self.state_db = state_db or _default_state_db()
        self.scan_interval_seconds = (
            float(scan_interval_seconds)
            if scan_interval_seconds is not None
            else float(os.getenv("S3_LOCATION_SCAN_INTERVAL_SECONDS", "30"))
        )
        self.fetch_rows = fetch_rows
        self.publisher = publisher
        self.stop_event = threading.Event()
        self._init_state_db()

    def _connect_state(self):
        directory = os.path.dirname(os.path.abspath(self.state_db))
        if directory:
            os.makedirs(directory, exist_ok=True)
        return sqlite3.connect(self.state_db)

    def _init_state_db(self) -> None:
        with closing(self._connect_state()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reported_locations (
                        gateway_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        reported_at TEXT NOT NULL,
                        PRIMARY KEY (gateway_id, node_id)
                    )
                    """
                )

    def _already_reported(self, node_id: str) -> bool:
        with closing(self._connect_state()) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM reported_locations
                WHERE gateway_id = ? AND node_id = ?
                LIMIT 1
                """,
                (self.gateway_id, node_id),
            ).fetchone()
        return row is not None

    def _mark_reported(self, node_id: str, latitude: float, longitude: float) -> None:
        reported_at = datetime.now(timezone.utc).isoformat()
        with closing(self._connect_state()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO reported_locations(
                        gateway_id, node_id, latitude, longitude, reported_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.gateway_id,
                        node_id,
                        latitude,
                        longitude,
                        reported_at,
                    ),
                )

    def report_once(self) -> int:
        reported = 0
        rows = list(self.fetch_rows() or [])

        for row in rows:
            node_id = str(row.get("node_id") or "").strip().upper()
            if not _NODE_RE.fullmatch(node_id):
                continue
            if self._already_reported(node_id):
                continue

            latitude = row.get("latitude")
            longitude = row.get("longitude")
            description = row.get("description")
            if not _valid_coordinate(latitude, longitude, description):
                continue

            lat = float(latitude)
            lon = float(longitude)
            payload = {
                "schema_version": 1,
                "event_type": "node.location",
                "gateway_id": self.gateway_id,
                "node_class": "node-zigbee",
                "transport": "zigbee",
                "node_id": node_id,
                "pole_node": row.get("pole_node"),
                "latitude": lat,
                "longitude": lon,
                "location_source": "s3_gateway_gps",
                "fix_status": "confirmed",
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }

            if not self.publisher(node_id, payload):
                continue

            self._mark_reported(node_id, lat, lon)
            reported += 1
            _LOG.info(
                "S3 node location reported gateway_id=%s node_id=%s latitude=%s longitude=%s",
                self.gateway_id,
                node_id,
                lat,
                lon,
            )

        return reported

    def run(self) -> None:
        _LOG.info(
            "S3 location reporter started gateway_id=%s interval=%ss state_db=%s",
            self.gateway_id,
            self.scan_interval_seconds,
            self.state_db,
        )
        while not self.stop_event.is_set():
            try:
                self.report_once()
            except Exception:
                _LOG.exception("S3 location reporter scan failed")

            if self.stop_event.wait(max(1.0, self.scan_interval_seconds)):
                break

        _LOG.info("S3 location reporter stopped gateway_id=%s", self.gateway_id)

    def stop(self) -> None:
        self.stop_event.set()


def create_location_reporter() -> S3LocationReporter:
    config = MQTTConfig.from_env()
    return S3LocationReporter(gateway_id=config.gateway_id)
