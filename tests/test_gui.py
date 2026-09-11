import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
import unittest
from unittest.mock import patch, Mock
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QGuiApplication, QKeyEvent
from macropad.gui import Controller
from macropad.shortcuts import encode
from macropad.model import label, VISIBLE_SLOTS

app = QGuiApplication.instance() or QGuiApplication([])


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.c = Controller(app, True)

    def tearDown(self):
        app.removeEventFilter(self.c)

    def test_demo_never_opens_hid(self):
        with patch("macropad.backend.enumerate_devices", side_effect=AssertionError("HID called")):
            c = Controller(app, True)
            c.candidates = {5}
            c.select(5)
            c.pending = "20004f00"
            c.save()
            self.assertEqual(c.ui["current"], "→")
            c.undo()
            self.assertEqual(c.ui["current"], "Volume +")
            app.removeEventFilter(c)

    def test_full_layout(self):
        self.assertEqual(len(self.c.ui["keys"]), 16)
        self.assertEqual(len(self.c.ui["dials"]), 3)
        self.assertEqual(len(VISIBLE_SLOTS), 25)

    def test_shift_p_capture(self):
        self.c.armed = True
        self.c.record()
        e = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ShiftModifier, "P")
        self.assertTrue(self.c.eventFilter(app, e))
        self.assertEqual(self.c.pending, "20021300")
        self.assertEqual(self.c.ui["pending"], "Shift + P")

    def test_modifier_alone_does_not_finish(self):
        self.c.armed = True
        self.c.record()
        self.c.eventFilter(app, QKeyEvent(QEvent.KeyPress, Qt.Key_Shift, Qt.ShiftModifier))
        self.assertTrue(self.c.recording)

    def test_escape_cancels(self):
        self.c.armed = True
        self.c.record()
        self.c.eventFilter(app, QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.assertFalse(self.c.recording)
        self.assertEqual(self.c.pending, "")

    def test_arrow_shortcuts(self):
        self.assertEqual(
            encode(QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)), "20004f00"
        )

    def test_unknown_assignment_is_lossless(self):
        self.assertIn("Custom", label("ffabcd12"))

    def test_unarmed_slot_cannot_save(self):
        self.c.verified = set()
        self.c.pending = "20021300"
        self.assertFalse(self.c.ui["canSave"])

    def test_click_and_record_cannot_start_editing(self):
        self.c.select(1)
        self.c.record()
        self.assertEqual(self.c.selected, 0)
        self.assertFalse(self.c.recording)
        self.assertFalse(self.c.armed)

    def test_physical_input_starts_confirmation(self):
        self.c.app = Mock(applicationState=lambda: Qt.ApplicationActive)
        self.c.on_input({"candidate_assignment_hex": self.c.value(0)})
        self.assertTrue(self.c.confirm)
        self.assertTrue(self.c.armed)
        self.c.record()
        self.assertTrue(self.c.recording)

    def test_duplicates_only_allow_matching_candidates(self):
        self.c.app = Mock(applicationState=lambda: Qt.ApplicationActive)
        self.c.on_input({"candidate_assignment_hex": self.c.value(5)})
        self.assertFalse(self.c.armed)
        self.assertIn(5, self.c.candidates)
        self.c.select(0)
        self.assertFalse(self.c.armed)
        self.c.select(5)
        self.assertTrue(self.c.armed)
        self.assertTrue(self.c.confirm)
        self.assertFalse(self.c.candidates)

    def test_reconnect_clears_error_and_edit_session(self):
        self.c.error = "read error"
        self.c.armed = True
        self.c.pending = "20021300"
        self.c.on_state({"connected": False})
        self.assertFalse(self.c.armed)
        self.assertFalse(self.c.pending)
        self.c.on_state(
            {
                "connected": True,
                "table": self.c.table.hex(),
                "writable": True,
                "input_available": True,
                "status": {"current_profile": 0},
                "verified": [0],
            }
        )
        self.assertEqual(self.c.error, "")

    def test_combined_save_waits_for_verification(self):
        self.c.demo = False
        self.c.worker = Mock()
        self.c.armed = True
        self.c.verified.clear()
        self.c.pending = "20021300"
        self.c.save()
        self.c.worker.submit.assert_called_once_with("calibrate", 0)
        self.c.verified.add(0)
        self.c.on_complete({"kind": "calibrated", "slot": 0})
        self.c.busy = False
        self.c.finish_verified_save()
        self.assertEqual(self.c.worker.submit.call_args.args[0], "save")

    def test_failed_verification_never_saves(self):
        self.c.demo = False
        self.c.worker = Mock()
        self.c.armed = True
        self.c.pending = "20021300"
        self.c.save_after_verify = True
        self.c.on_fault("Disconnected during test")
        self.c.finish_verified_save()
        self.c.worker.submit.assert_not_called()
