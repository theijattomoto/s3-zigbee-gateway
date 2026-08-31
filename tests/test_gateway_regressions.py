import importlib.util
import pathlib
import sys
import threading
import time
import types
import unittest
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GATEWAY_PACKAGE = REPO_ROOT / "pyserialgateway" / "PYGatewayListener"


def load_module_from_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_main_listener_module():
    package_name = "gateway_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = [str(GATEWAY_PACKAGE)]
    sys.modules[package_name] = package

    for dependency_name, class_name in (
        ("gps_thread", "GPSThread"),
        ("recovery_thread", "RecoveryThread"),
        ("timetable_thread", "TimetableThread"),
    ):
        dependency = types.ModuleType(f"{package_name}.{dependency_name}")
        setattr(dependency, class_name, type(class_name, (), {}))
        sys.modules[dependency.__name__] = dependency

    return load_module_from_path(
        f"{package_name}.main_listener_thread",
        GATEWAY_PACKAGE / "main_listener_thread.py",
    )


class SerialObjectManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serial_manager = load_module_from_path(
            "gateway_serial_manager_under_test",
            GATEWAY_PACKAGE / "serial_manager.py",
        )

    def test_write_calls_are_serialized(self):
        manager = self.serial_manager.SerialObjectManager(port=None)
        active_writers = 0
        max_active_writers = 0
        state_lock = threading.Lock()

        def fake_serial_write(_self, data):
            nonlocal active_writers, max_active_writers
            with state_lock:
                active_writers += 1
                max_active_writers = max(max_active_writers, active_writers)
            time.sleep(0.03)
            with state_lock:
                active_writers -= 1
            return len(data)

        with mock.patch.object(
            self.serial_manager.serial.Serial,
            "write",
            new=fake_serial_write,
        ):
            threads = [
                threading.Thread(target=manager.write, args=(b"+PM0001\r\n",)),
                threading.Thread(target=manager.write, args=(b"+DR0002\r\n",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=1)

        self.assertEqual(max_active_writers, 1)

    def test_force_close_unlocks_own_descriptor_and_closes_port(self):
        manager = self.serial_manager.SerialObjectManager(port=None)
        manager.is_open = True

        try:
            with (
                mock.patch.object(manager, "fileno", return_value=42) as fileno,
                mock.patch.object(manager, "close") as close,
                mock.patch.object(self.serial_manager.fcntl, "flock") as flock,
            ):
                manager.force_close()

            fileno.assert_called_once_with()
            flock.assert_called_once_with(42, self.serial_manager.fcntl.LOCK_UN)
            close.assert_called_once_with()
        finally:
            manager.is_open = False


class MainListenerPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listener_module = load_main_listener_module()

    def make_listener(self):
        return self.listener_module.MainListenerThread(
            False,
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            [],
            [],
            None,
            b"",
            mock.Mock(),
            ["D0"],
            ["E1", "E2", "E4", "H1", "H2", "G0", "P0"],
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
            mock.Mock(),
        )

    def test_packet_snipping_extracts_concatenated_frames(self):
        listener = self.make_listener()
        packet = b"#H1|0001|alpha#\r\n#H1|0002|beta#\r\n"

        node_ids, frames = listener.packet_snipping(packet, "#H1|")

        self.assertEqual(node_ids, ["0001", "0002"])
        self.assertEqual(
            frames,
            [b"#H1|0001|alpha#", b"#H1|0002|beta#"],
        )

    def test_header_filter_discards_garbage_prefix(self):
        listener = self.make_listener()
        listener.packet = b"garbage\x00\xff#E2|00AA|payload#\r\n"

        filtered = listener.data_headerfilter()

        self.assertEqual(filtered, b"#E2|00AA|payload#\r\n")


class NoSerialStartupRegressionTests(unittest.TestCase):
    def test_no_serial_port_exits_before_listener_loop(self):
        source = (GATEWAY_PACKAGE / "main.py").read_text(encoding="utf-8")

        guard = source.index("if not port_status:")
        exit_message = source.index(
            "No Zigbee gateway serial port detected. Gateway listener exiting."
        )
        listener_start = source.index(
            "spec_string = '[START] PYGATEWAY LISTENER @ '"
        )
        listener_loop = source.index("while True:", listener_start)

        self.assertLess(guard, exit_message)
        self.assertLess(exit_message, listener_start)
        self.assertLess(listener_start, listener_loop)


class ForcedPortSwitchRegressionTests(unittest.TestCase):
    def test_previous_port_is_compared_before_last_index_is_cleared(self):
        source = (GATEWAY_PACKAGE / "main.py").read_text(encoding="utf-8")

        save_index = source.index("previous_port_index = last_port_index")
        comparison = source.index("if previous_port_index != retry_port_index:")
        clear_index = source.index("last_port_index = None", save_index)

        self.assertLess(save_index, comparison)
        self.assertLess(comparison, clear_index)


if __name__ == "__main__":
    unittest.main()
