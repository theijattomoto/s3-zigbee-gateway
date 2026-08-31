"""SQLite-backed durable buffer for replayable MQTT messages."""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from typing import Iterable, Tuple


class MQTTBuffer:
    def __init__(self, path: str, retention_days: int = 7):
        self.path = path
        self.retention_days = retention_days
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS buffered_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        qos INTEGER NOT NULL,
                        retain INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    def put(self, topic: str, payload: str, qos: int, retain: bool = False) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO buffered_messages(topic,payload,qos,retain) VALUES(?,?,?,?)",
                    (topic, payload, int(qos), int(bool(retain))),
                )

    def pending(self) -> Iterable[Tuple[int, str, str, int, bool]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id,topic,payload,qos,retain FROM buffered_messages ORDER BY id ASC"
            ).fetchall()
        return [(r[0], r[1], r[2], int(r[3]), bool(r[4])) for r in rows]

    def delete(self, message_id: int) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("DELETE FROM buffered_messages WHERE id = ?", (message_id,))

    def cleanup(self) -> int:
        cutoff = (datetime.now() - timedelta(days=self.retention_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "DELETE FROM buffered_messages WHERE created_at < ?", (cutoff,)
                )
                return cur.rowcount
