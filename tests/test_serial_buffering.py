import importlib.util
import pathlib
import sys
import unittest
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIAL_MANAGER_PATH = (
    REPO_ROOT / "pyserialgateway" / "PYGatewayListener" / "serial_manager.py"
)


def load_serial_manager_module():
    module_name = "gateway_serial_buffering_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SERIAL_MANAGER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class SerialBufferingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_serial_manager_module()

    def make_manager(self):
        return self.module.SerialObjectManager(port=None)

    def test_partial_poll_echo_is_reassembled(self):
        manager = self.make_manager()

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            side_effect=[b"+", b"PM8E9E\r\n"],
        ):
            frame = manager.read_until(b"\r\n")

        self.assertEqual(frame, b"+PM8E9E\r\n")
        self.assertEqual(manager._rx_buffer, bytearray())

    def test_timeout_preserves_partial_bytes_for_next_call(self):
        manager = self.make_manager()

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            side_effect=[b"+P", b"", b"M8EAF\r\n"],
        ):
            first = manager.read_until(b"\r\n")
            second = manager.read_until(b"\r\n")

        self.assertEqual(first, b"")
        self.assertEqual(second, b"+PM8EAF\r\n")
        self.assertEqual(manager._rx_buffer, bytearray())

    def test_legacy_string_delimiter_is_supported(self):
        manager = self.make_manager()

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            return_value=b"SN: 1 HW: 1 NodeID: FE01 PanID: 1001 ZM-FW: 1\r\n",
        ) as read_until:
            frame = manager.read_until("\r\n")

        self.assertTrue(frame.endswith(b"\r\n"))
        read_until.assert_called_once_with(b"\r\n", size=None)


if __name__ == "__main__":
    unittest.main()
