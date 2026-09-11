import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
import unittest
from unittest.mock import patch
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
        self.c.record()
        e = QKeyEvent(QEvent.KeyPress, Qt.Key_P, Qt.ShiftModifier, "P")
        self.assertTrue(self.c.eventFilter(app, e))
        self.assertEqual(self.c.pending, "20021300")
        self.assertEqual(self.c.ui["pending"], "Shift + P")

    def test_modifier_alone_does_not_finish(self):
        self.c.record()
        self.c.eventFilter(app, QKeyEvent(QEvent.KeyPress, Qt.Key_Shift, Qt.ShiftModifier))
        self.assertTrue(self.c.recording)

    def test_escape_cancels(self):
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

    def test_unverified_slot_cannot_save(self):
        self.c.verified = set()
        self.c.pending = "20021300"
        self.assertFalse(self.c.ui["canSave"])
