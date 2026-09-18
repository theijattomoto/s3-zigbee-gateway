import os
import tempfile
import unittest

from pyserialgateway.PYGatewayListener.location_reporter import (
    S3LocationReporter,
    _eligible_inventory_row,
    _valid_coordinate,
)


class LocationReporterTests(unittest.TestCase):
    def make_state_db(self):
        temp = tempfile.NamedTemporaryFile(suffix=".location.db", delete=False)
        temp.close()
        self.addCleanup(lambda: os.path.exists(temp.name) and os.unlink(temp.name))
        return temp.name

    def test_valid_coordinate_rejects_gateway_reference_zero(self):
        self.assertFalse(_valid_coordinate("3.069900", "101.692244", "#G0!"))
        self.assertFalse(_valid_coordinate("3.069900", "101.692244", "#G0"))
        self.assertFalse(_valid_coordinate("0", "0", "#G0"))
        self.assertFalse(_valid_coordinate("invalid", "101.7", "#G0"))
        self.assertFalse(_valid_coordinate("3.123456", "101.654321", "#G0-"))
        self.assertTrue(_valid_coordinate("3.123456", "101.654321", "#G0"))

    def test_inventory_filter_rejects_non_lantern_rows(self):
        self.assertFalse(_eligible_inventory_row({"pole_node": None}))
        self.assertFalse(_eligible_inventory_row({"pole_node": ""}))
        self.assertFalse(_eligible_inventory_row({"pole_node": "TBD-AUTO"}))
        self.assertFalse(_eligible_inventory_row({"pole_node": "GW-1"}))
        self.assertFalse(_eligible_inventory_row({"pole_node": "GW-2"}))
        self.assertTrue(_eligible_inventory_row({"pole_node": "R-48"}))

    def test_duplicate_node_identity_fails_closed(self):
        rows = [
            {
                "node_id": "0148",
                "pole_node": "R-1",
                "latitude": "3.0675",
                "longitude": "101.68768833333333",
                "description": "#G0",
            },
            {
                "node_id": "0148",
                "pole_node": "R-1",
                "latitude": "3.0675",
                "longitude": "101.68768833333333",
                "description": "#G0",
            },
        ]
        published = []

        reporter = S3LocationReporter(
            gateway_id="s3-gw-01",
            state_db=self.make_state_db(),
            fetch_rows=lambda: rows,
            publisher=lambda node_id, payload: published.append(
                (node_id, payload)
            ) or True,
        )

        self.assertEqual(reporter.report_once(), 0)
        self.assertEqual(published, [])

    def test_reports_valid_location_once_and_persists_state(self):
        rows = [
            {
                "node_id": "8EED",
                "pole_node": "R-1",
                "latitude": "3.123456",
                "longitude": "101.654321",
                "description": "#G0",
            }
        ]
        published = []

        def publisher(node_id, payload):
            published.append((node_id, payload))
            return True

        state_db = self.make_state_db()
        reporter = S3LocationReporter(
            gateway_id="s3-gw-01",
            state_db=state_db,
            fetch_rows=lambda: rows,
            publisher=publisher,
        )

        self.assertEqual(reporter.report_once(), 1)
        self.assertEqual(reporter.report_once(), 0)
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0][0], "8EED")
        self.assertEqual(published[0][1]["event_type"], "node.location")
        self.assertEqual(published[0][1]["gateway_id"], "s3-gw-01")
        self.assertEqual(published[0][1]["latitude"], 3.123456)
        self.assertEqual(published[0][1]["longitude"], 101.654321)

        after_restart = S3LocationReporter(
            gateway_id="s3-gw-01",
            state_db=state_db,
            fetch_rows=lambda: rows,
            publisher=publisher,
        )
        self.assertEqual(after_restart.report_once(), 0)
        self.assertEqual(len(published), 1)

    def test_failed_publish_is_retried_and_not_marked_reported(self):
        rows = [
            {
                "node_id": "0111",
                "pole_node": "R-48",
                "latitude": "3.200000",
                "longitude": "101.700000",
                "description": "#G0",
            }
        ]
        attempts = []

        def publisher(node_id, payload):
            attempts.append(node_id)
            return len(attempts) >= 2

        reporter = S3LocationReporter(
            gateway_id="s3-gw-01",
            state_db=self.make_state_db(),
            fetch_rows=lambda: rows,
            publisher=publisher,
        )

        self.assertEqual(reporter.report_once(), 0)
        self.assertEqual(reporter.report_once(), 1)
        self.assertEqual(reporter.report_once(), 0)
        self.assertEqual(attempts, ["0111", "0111"])

    def test_invalid_or_fallback_rows_are_never_published(self):
        rows = [
            {
                "node_id": "8EED",
                "pole_node": "R-1",
                "latitude": "3.069900",
                "longitude": "101.692244",
                "description": "#G0!",
            },
            {
                "node_id": "BAD",
                "pole_node": "R-2",
                "latitude": "3.100000",
                "longitude": "101.700000",
                "description": "#G0",
            },
        ]
        published = []

        reporter = S3LocationReporter(
            gateway_id="s3-gw-01",
            state_db=self.make_state_db(),
            fetch_rows=lambda: rows,
            publisher=lambda node_id, payload: published.append((node_id, payload)) or True,
        )

        self.assertEqual(reporter.report_once(), 0)
        self.assertEqual(published, [])


if __name__ == "__main__":
    unittest.main()
