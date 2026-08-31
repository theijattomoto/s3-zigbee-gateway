import unittest
from unittest.mock import MagicMock, patch

from pyserialgateway.PYGatewayListener.database_thread import DatabaseThread


class RecordingQueue:
    def __init__(self):
        self.items = []

    def put(self, item, *args, **kwargs):
        self.items.append((item, args, kwargs))
        return None


class DatabaseMQTTIntegrationTests(unittest.TestCase):
    def test_new_valid_h1_packet_reaches_http_and_mqtt_mirror(self):
        packet_logger = MagicMock()
        problem_logger = MagicMock()
        http_queue = RecordingQueue()
        packet = b"#H1|001A|0001|01-00:00:00|...#"

        db_thread = DatabaseThread(
            packet_logger=packet_logger,
            problem_logger=problem_logger,
            msg_queue=http_queue,
            node_ID_list=["001A"],
            node_ID_datalist=[packet],
            ack="H1",
            dtime_list=["2026-09-01 00:00:00"],
            message_ID_list=["0001"],
            override_flag_list=[False],
            lamp_status_list=[True],
        )

        with patch.object(db_thread, "postgres_fetch", return_value=[]), patch.object(
            db_thread, "postgres_update"
        ) as postgres_update, patch(
            "pyserialgateway.mqtt_service.mirroring.mirror_validated_packet"
        ) as mirror:
            db_thread.run()

        postgres_update.assert_called_once()
        self.assertEqual(len(http_queue.items), 1)
        self.assertEqual(http_queue.items[0][0], ("001A", packet, 0))
        mirror.assert_called_once_with(
            node_id="001A",
            node_data=packet,
            packet_type="H1",
        )

    def test_existing_duplicate_h1_packet_is_not_forwarded_or_mirrored(self):
        packet_logger = MagicMock()
        problem_logger = MagicMock()
        http_queue = RecordingQueue()
        packet = b"#H1|001A|0001|01-00:00:00|...#"

        db_thread = DatabaseThread(
            packet_logger=packet_logger,
            problem_logger=problem_logger,
            msg_queue=http_queue,
            node_ID_list=["001A"],
            node_ID_datalist=[packet],
            ack="H1",
            dtime_list=["2026-09-01 00:00:00"],
            message_ID_list=["0001"],
            override_flag_list=[False],
            lamp_status_list=[True],
        )

        existing_record = [
            (
                __import__("datetime").datetime(2026, 9, 1, 0, 0, 0),
                "0001",
                0,
                0,
                0,
            )
        ]

        with patch.object(db_thread, "postgres_fetch", return_value=existing_record), patch.object(
            db_thread, "postgres_update"
        ) as postgres_update, patch(
            "pyserialgateway.mqtt_service.mirroring.mirror_validated_packet"
        ) as mirror:
            db_thread.run()

        postgres_update.assert_not_called()
        self.assertEqual(http_queue.items, [])
        mirror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
