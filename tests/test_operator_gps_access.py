import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "setup-operator-gps-access.sh"


class OperatorGpsAccessScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_operator_gps_directory_is_exposed(self):
        self.assertIn('OPERATOR_GPS_DIR="$OPERATOR_DIR/GPSlog"', self.source)
        self.assertIn('RUNTIME_GPS_DIR="$TARGET_DIR/PYSerialGateway/GPSlog"', self.source)
        self.assertIn('ln -s "$OPERATOR_GPS_DIR" "$RUNTIME_GPS_DIR"', self.source)

    def test_existing_gps_history_is_backed_up_before_runtime_directory_removal(self):
        backup = self.source.index('rsync -a "$RUNTIME_GPS_DIR/" "$BACKUP_DIR/GPSlog-legacy/"')
        operator_copy = self.source.index('rsync -a --ignore-existing "$RUNTIME_GPS_DIR/" "$OPERATOR_GPS_DIR/"')
        removal = self.source.index('rm -rf "$RUNTIME_GPS_DIR"')

        self.assertLess(backup, removal)
        self.assertLess(operator_copy, removal)

    def test_unexpected_existing_symlink_is_not_overwritten(self):
        self.assertIn('Refusing to replace unexpected GPSlog symlink', self.source)

    def test_service_account_write_access_is_verified(self):
        self.assertIn('runuser -u s3gw -- test -w "$OPERATOR_GPS_DIR"', self.source)
        self.assertIn('GPSlog symlink verification failed.', self.source)


if __name__ == "__main__":
    unittest.main()
