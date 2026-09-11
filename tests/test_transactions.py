import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from macropad.model import demo_table
from macropad.transactions import write_one, TransactionError, packet
from macropad.storage import load


class Audit:
    def record(self, *args, **kwargs):
        pass


class FakeReader:
    def __init__(self, directory):
        self.audit = Audit()
        self.device = self
        self.directory = Path(directory)
        self.tables = {p: bytearray(demo_table()) for p in range(6)}
        self.writes = []
        self.ack = b""
        self.bad_ack = False
        self.corrupt = False
        self.profile = 0

    def status(self):
        return dict(
            version=1,
            internal_pid=0x246D,
            firmware=100,
            profile_count=6,
            layer_count=1,
            current_profile=self.profile,
            current_layer=0,
        )

    def memory(self, command, size, profile):
        return bytes(self.tables[profile][:size])

    def write(self, data):
        assert list(self.directory.glob("*-before.json")), "A backup must exist before writing"
        self.writes.append(data)
        slot = data[4] // 4
        value = data[9:13]
        self.tables[0][slot * 4 : slot * 4 + 4] = value
        if self.corrupt:
            self.tables[0][28:32] = b"\0" * 4
        self.ack = bytes([0xAA, 16, 1]) + bytes(5) + value + bytes(52)
        return len(data)

    def read(self, size, timeout):
        return bytes(64) if self.bad_ack else self.ack


class TransactionTests(unittest.TestCase):
    def test_save_and_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            result = write_one(r, {"serial_number": "test"}, 0, "20021300", "20005f00", folder)
            self.assertTrue(result["verified"])
            self.assertEqual(result["changes"], [("0", 0, "20005f00", "20021300")])
            self.assertEqual(load(result["backup"])["before"], "20005f00")
            restored = write_one(r, {}, 0, "20005f00", "20021300", folder, "restore")
            self.assertTrue(restored["verified"])

    def test_backup_failure_prevents_write(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            with patch("macropad.transactions.save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    write_one(r, {}, 0, "20021300", "20005f00", folder)
            self.assertEqual(r.writes, [])

    def test_stale_value_prevents_write(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            with self.assertRaises(ValueError):
                write_one(r, {}, 0, "20021300", "20000000", folder)
            self.assertEqual(r.writes, [])

    def test_unexpected_other_change_is_error(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            r.corrupt = True
            with self.assertRaises(TransactionError):
                write_one(r, {}, 0, "20021300", "20005f00", folder)
            self.assertEqual(len(list(Path(folder).glob("*-error.json"))), 1)

    def test_bad_ack_never_reports_success(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            r.bad_ack = True
            with self.assertRaises(TransactionError):
                write_one(r, {}, 0, "20021300", "20005f00", folder)

    def test_unknown_profile_prevents_write(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            r.profile = 1
            with self.assertRaises(ValueError):
                write_one(r, {}, 0, "20021300", "20005f00", folder)
            self.assertEqual(r.writes, [])

    def test_invalid_slot_prevents_packet(self):
        for slot in (-1, 25, 27, 144):
            with self.assertRaises(ValueError):
                packet(slot, b"\x20\x00\x13\x00")

    def test_restore_preserves_original_media_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            r = FakeReader(folder)
            write_one(r, {}, 5, "20004f00", "30e90000", folder)
            result = write_one(r, {}, 5, "30e90000", "20004f00", folder, "restore")
            self.assertTrue(result["verified"])
