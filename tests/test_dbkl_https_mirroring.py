import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "pyserialgateway" / "PYGatewayListener" / "http_thread.py"


def load_http_thread_module():
    package_name = "dbkl_http_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = [str(MODULE_PATH.parent)]
    sys.modules[package_name] = package

    config = types.ModuleType(f"{package_name}.config")
    config.auth_key_pair = ["dbkl.example.com", "443", "user", "password"]
    config.cert_location = "/tmp/client.pem"
    sys.modules[config.__name__] = config

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.http_thread",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeQueue:
    def qsize(self):
        return 0

    def task_done(self):
        pass


class DBKLHTTPSMirroringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_http_thread_module()

    def make_thread(self, **env):
        options = {
            "NOSELMOS": False,
            "NOAUTH": False,
            "TESTUP": False,
        }
        with mock.patch.dict("os.environ", env, clear=False):
            return self.module.MainHTTPURLThread(
                mock.Mock(),
                mock.Mock(),
                mock.Mock(),
                FakeQueue(),
                "http://rest.example.com/api/heartbeat?site=s3",
                0,
                options,
                False,
            )

    def test_legacy_dbkl_url_preserves_path_and_query(self):
        url = self.module.build_dbkl_https_url(
            "http://rest.example.com/api/heartbeat?site=s3",
            ["dbkl.example.com", "443", "user", "password"],
        )
        self.assertEqual(
            url,
            "https://dbkl.example.com:443/api/heartbeat?site=s3",
        )

    def test_explicit_dbkl_url_overrides_legacy_derivation(self):
        url = self.module.build_dbkl_https_url(
            "http://rest.example.com/api/heartbeat",
            ["legacy.example.com", "443", "user", "password"],
            explicit_url="https://dbkl.example.com/custom/ingest",
        )
        self.assertEqual(url, "https://dbkl.example.com/custom/ingest")

    def test_rest_failure_does_not_block_dbkl_attempt(self):
        thread = self.make_thread()
        indata = b"ack_code=H1&node_id=001A"

        with mock.patch.object(thread, "_send_request") as send_request:
            send_request.side_effect = [
                OSError("REST unavailable"),
                None,
            ]
            with mock.patch.object(self.module.ssl.SSLContext, "load_cert_chain"):
                thread._send_primary_rest(indata, "001A")
                thread._send_dbkl_https(indata, "001A")

        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(
            send_request.call_args_list[1].args[0],
            "https://dbkl.example.com:443/api/heartbeat?site=s3",
        )

    def test_testup_suppresses_dbkl_delivery(self):
        options = {
            "NOSELMOS": False,
            "NOAUTH": False,
            "TESTUP": True,
        }
        thread = self.module.MainHTTPURLThread(
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            FakeQueue(),
            "http://rest.example.com/api/heartbeat",
            0,
            options,
            False,
        )

        with mock.patch.object(thread, "_send_request") as send_request:
            thread._send_dbkl_https(b"payload", "001A")

        send_request.assert_not_called()

    def test_dbkl_mirroring_can_be_disabled_by_environment(self):
        thread = self.make_thread(DBKL_HTTPS_ENABLED="false")

        with mock.patch.object(thread, "_send_request") as send_request:
            thread._send_dbkl_https(b"payload", "001A")

        send_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
