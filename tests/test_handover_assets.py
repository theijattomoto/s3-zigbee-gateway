import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HandoverAssetsTests(unittest.TestCase):
    def test_base_systemd_unit_runs_as_s3gw_with_serial_group(self):
        text = (ROOT / 'deploy/systemd/s3-zigbee-gateway.service').read_text()
        self.assertIn('User=s3gw', text)
        self.assertIn('Group=s3gw', text)
        self.assertIn('SupplementaryGroups=dialout', text)
        self.assertIn('EnvironmentFile=/opt/s3-gateway/app/.env', text)
        self.assertIn('ExecStart=/opt/s3-gateway/app/PYSerialGateway/run-service.sh', text)

    def test_bootstrap_installs_required_os_packages(self):
        text = (ROOT / 'scripts/bootstrap-production-pi.sh').read_text()
        self.assertIn('apt-get update', text)
        self.assertIn('apt-get install -y', text)
        for package in (
            'python3-venv', 'postgresql', 'postgresql-client',
            'rsync', 'acl', 'usbutils'
        ):
            self.assertIn(package, text)

    def test_bootstrap_prepares_service_account_serial_access(self):
        text = (ROOT / 'scripts/bootstrap-production-pi.sh').read_text()
        self.assertIn('usermod -a -G dialout', text)
        self.assertIn("grep -qx dialout", text)

    def test_bootstrap_refuses_existing_runtime(self):
        text = (ROOT / 'scripts/bootstrap-production-pi.sh').read_text()
        self.assertIn('Refusing fresh bootstrap because target is not empty', text)
        self.assertIn('Use deploy-production.sh for an existing gateway.', text)

    def test_bootstrap_creates_hardened_database_owner(self):
        text = (ROOT / 'scripts/bootstrap-production-pi.sh').read_text()
        self.assertIn('createdb -O "$SERVICE_USER" "$DB_NAME"', text)
        self.assertIn('ALTER TABLE node_database OWNER TO ${SERVICE_USER};', text)
        self.assertIn('ALTER TABLE filter_time_py OWNER TO ${SERVICE_USER};', text)

    def test_bootstrap_requires_followup_deploy_and_acceptance(self):
        text = (ROOT / 'scripts/bootstrap-production-pi.sh').read_text()
        self.assertIn('sudo ./scripts/deploy-production.sh', text)
        self.assertIn('sudo bash scripts/install-log-retention.sh', text)
        self.assertIn('sudo s3-gateway-dbup', text)
        self.assertIn('sudo bash scripts/validate-handover.sh', text)

    def test_dbup_is_serial_independent_and_verified(self):
        wrapper = (ROOT / 'scripts/s3-gateway-dbup').read_text()
        sync = (ROOT / 'scripts/dbup_sync.py').read_text()
        self.assertIn('dbup_sync.py', wrapper)
        self.assertNotIn('DBUP_ONLY', wrapper)
        self.assertIn('DBUP sync verification: PASS', sync)
        self.assertIn('PostgreSQL node_database does not match operator CSV/GW config', sync)
        self.assertNotIn('SerialObjectManager', sync)

    def test_handover_docs_exist(self):
        for path in (
            'README.md',
            'docs/README.md',
            'docs/HANDOVER_INDEX.md',
            'docs/HANDOVER_PROJECT_TEAM_OPERATIONS.md',
            'docs/HANDOVER_PRODUCTION_TEAM_BUILD.md',
            'docs/TECHNICAL_ARCHITECTURE.md',
        ):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_documentation_has_no_chat_only_citation_tokens(self):
        docs = [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md'))]
        for path in docs:
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('filecite', text, path)
            self.assertNotIn('turn146file0', text, path)

    def test_readme_links_to_role_based_handover_docs(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('docs/HANDOVER_PROJECT_TEAM_OPERATIONS.md', text)
        self.assertIn('docs/HANDOVER_PRODUCTION_TEAM_BUILD.md', text)
        self.assertIn('docs/TECHNICAL_ARCHITECTURE.md', text)


if __name__ == '__main__':
    unittest.main()
