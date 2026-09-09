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

    def test_startup_mode_uses_legacy_pyserial_read(self):
        manager = self.make_manager()

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            return_value=b"SN: 1 HW: 1 NodeID: FE01 PanID: 1001 ZM-FW: 1\r\n",
        ) as read_until:
            frame = manager.read_until("\r\n")

        self.assertIn(b"SN: 1", frame)
        read_until.assert_called_once_with("\r\n", size=None)
        self.assertFalse(manager._runtime_buffering_enabled)

    def test_partial_poll_echo_is_reassembled_in_runtime_mode(self):
        manager = self.make_manager()
        manager._runtime_buffering_enabled = True

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            side_effect=[b"+", b"PM8E9E\r\n"],
        ):
            frame = manager.read_until(b"\r\n")

        self.assertEqual(frame, b"+PM8E9E\r\n")
        self.assertEqual(manager._runtime_rx_buffer, bytearray())

    def test_timeout_preserves_partial_bytes_for_next_runtime_call(self):
        manager = self.make_manager()
        manager._runtime_buffering_enabled = True

        with mock.patch.object(
            self.module.serial.Serial,
            "read_until",
            side_effect=[b"+P", b"", b"M8EAF\r\n"],
        ):
            first = manager.read_until(b"\r\n")
            second = manager.read_until(b"\r\n")

        self.assertEqual(first, b"")
        self.assertEqual(second, b"+PM8EAF\r\n")
        self.assertEqual(manager._runtime_rx_buffer, bytearray())

    def test_gw_initial_forces_legacy_mode_then_enables_runtime_buffering(self):
        manager = self.make_manager()
        manager.is_open = True
        manager.GW_datalist = [("FE01", "1001", "11")]
        manager.lastportindex = 0
        manager.SN_info = None
        manager.logger = mock.Mock()
        manager.simple_logger = mock.Mock()

        ds_response = b"SN: 1 HW: 1 NodeID: FE01 PanID: 1001 ZM-FW: 1\r\n"

        with (
            mock.patch.object(manager, "write") as write,
            mock.patch.object(
                self.module.serial.Serial,
                "read_until",
                return_value=ds_response,
            ) as base_read_until,
        ):
            status, data = manager.gw_initial(0, 1)

        self.assertTrue(status)
        self.assertEqual(data, ("FE01", "1001", "11"))
        base_read_until.assert_called_once_with("\r\n", size=None)
        write.assert_any_call(b"+DS\r\n")
        write.assert_any_call(b"+ZCFE01100111\r\n")
        self.assertTrue(manager._runtime_buffering_enabled)


if __name__ == "__main__":
    unittest.main()
