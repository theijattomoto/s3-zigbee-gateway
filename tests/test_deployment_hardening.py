import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = (REPO_ROOT / "scripts" / "deploy-production.sh").read_text(encoding="utf-8")
GPS_HELPER = (REPO_ROOT / "scripts" / "setup-operator-gps-access.sh").read_text(encoding="utf-8")
HARDENING = (REPO_ROOT / "scripts" / "install-runtime-hardening.sh").read_text(encoding="utf-8")
GPSUP_DROPIN = (REPO_ROOT / "deploy" / "systemd" / "s3-zigbee-gateway-gpsup.conf").read_text(encoding="utf-8")
SUDOERS = (REPO_ROOT / "deploy" / "sudoers" / "s3-gateway-hwreset").read_text(encoding="utf-8")
README = (REPO_ROOT / "PYSerialGateway" / "README-OPERATOR.md").read_text(encoding="utf-8")


class DeploymentHardeningTests(unittest.TestCase):
    def test_gpsup_is_managed_by_systemd_dropin(self):
        self.assertIn("ExecStart=/opt/s3-gateway/app/PYSerialGateway/run-service.sh GPSUP", GPSUP_DROPIN)
        self.assertIn('run-service.sh GPSUP', HARDENING)
        self.assertIn('pygw_main.py GPSUP', DEPLOY)

    def test_restricted_sudo_rule_is_exact(self):
        expected = (
            "s3gw ALL=(root) NOPASSWD: /usr/bin/python3 "
            "/opt/s3-gateway/app/pyserialgateway/hardware_reset.py"
        )
        self.assertEqual(SUDOERS.strip(), expected)
        self.assertNotIn("NOPASSWD: ALL", SUDOERS)
        self.assertIn('visudo -cf "$SUDOERS_FILE"', HARDENING)

    def test_privileged_reset_path_is_protected(self):
        self.assertIn('chmod 755 "$TARGET_DIR" "$TARGET_DIR/pyserialgateway"', HARDENING)
        self.assertIn('chown root:root "$RESET_SCRIPT" "$RESET_CONFIG"', HARDENING)
        self.assertIn('runuser -u s3gw -- test -w "$RESET_SCRIPT"', HARDENING)
        self.assertIn('runuser -u s3gw -- test -w "$RESET_CONFIG"', HARDENING)

    def test_deploy_runs_gps_migration_before_hardening_and_start(self):
        gps = DEPLOY.index('bash "$SOURCE_DIR/scripts/setup-operator-gps-access.sh"')
        hardening = DEPLOY.index('bash "$SOURCE_DIR/scripts/install-runtime-hardening.sh"')
        start = DEPLOY.index('systemctl start "$SERVICE_NAME"', hardening)
        self.assertLess(gps, hardening)
        self.assertLess(hardening, start)

    def test_deploy_does_not_recreate_private_gps_directory(self):
        runtime_block = DEPLOY[DEPLOY.index("# Normal runtime log directories"):DEPLOY.index("# Operator logs")]
        self.assertNotIn('PYSerialGateway/GPSlog', runtime_block.split('install -d', 1)[-1])
        self.assertIn('readlink -f "$TARGET_DIR/PYSerialGateway/GPSlog"', DEPLOY)

    def test_gps_helper_reapplies_acl_after_legacy_rsync(self):
        copy = GPS_HELPER.index('rsync -a --ignore-existing "$RUNTIME_GPS_DIR/" "$OPERATOR_GPS_DIR/"')
        reapply = GPS_HELPER.index('apply_operator_gps_permissions', copy)
        symlink = GPS_HELPER.index('ln -s "$OPERATOR_GPS_DIR" "$RUNTIME_GPS_DIR"')
        self.assertLess(copy, reapply)
        self.assertLess(reapply, symlink)

    def test_operator_readme_documents_managed_recovery_state(self):
        self.assertIn("pygw_main.py GPSUP", README)
        self.assertIn("/etc/sudoers.d/s3-gateway-hwreset", README)
        self.assertIn("~/S3Gateway/GPSlog/", README)


if __name__ == "__main__":
    unittest.main()
