import tempfile
import unittest
from pathlib import Path
from macropad.worker import DeviceWorker
from macropad.storage import load
from test_transactions import FakeReader


class WorkerTests(unittest.TestCase):
    def worker(self, folder):
        worker = DeviceWorker(folder)
        worker.reader = FakeReader(Path(folder) / "backups")
        worker.identity = {"vendor_id": 0x36AE, "product_id": 0x2475, "serial_number": "test"}
        worker.monitors = [({}, None)]
        return worker

    def test_temporary_marker_is_journaled_and_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            w = self.worker(folder)
            old = bytes(w.reader.tables[0][4:8])
            w.handle("calibrate", (1,))
            self.assertTrue(w.pending.exists())
            journal = load(w.pending)
            self.assertNotEqual(bytes(w.reader.tables[0][4:8]), old)
            self.assertEqual(journal["before"], old.hex())
            w.restore_pending()
            self.assertEqual(bytes(w.reader.tables[0][4:8]), old)
            self.assertFalse(w.pending.exists())

    def test_pending_test_blocks_normal_save(self):
        with tempfile.TemporaryDirectory() as folder:
            w = self.worker(folder)
            w.handle("calibrate", (1,))
            with self.assertRaises(ValueError):
                w.handle("save", (0, "20021300", "20005f00"))
            w.restore_pending()

    def test_restore_does_not_overwrite_external_change(self):
        with tempfile.TemporaryDirectory() as folder:
            w = self.worker(folder)
            w.handle("calibrate", (1,))
            w.reader.tables[0][4:8] = bytes.fromhex("20000500")
            with self.assertRaises(ValueError):
                w.restore_pending()
            self.assertTrue(w.pending.exists())

    def test_unverified_control_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            w = self.worker(folder)
            with self.assertRaises(ValueError):
                w.handle("save", (1, "20021300", "20006000"))
            self.assertEqual(w.reader.writes, [])

    def test_marker_restoration_checks_device_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            w = self.worker(folder)
            w.handle("calibrate", (1,))
            w.identity["serial_number"] = "another-pad"
            with self.assertRaises(ValueError):
                w.restore_pending()
            self.assertTrue(w.pending.exists())
