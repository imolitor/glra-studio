# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
import unittest
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtCore import QUrl, Qt, QPointF, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from macropad.gui import Controller

app = QGuiApplication.instance() or QGuiApplication([])


class QmlTests(unittest.TestCase):
    def test_click_record_save_undo_and_render(self):
        controller = Controller(app, True)
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda items: warnings.extend(str(i) for i in items))
        engine.rootContext().setContextProperty("studio", controller)
        engine.load(QUrl.fromLocalFile(str(Path(__file__).parents[1] / "macropad/qml/Main.qml")))
        self.assertTrue(engine.rootObjects())
        window = engine.rootObjects()[0]
        self.assertIsInstance(window, QQuickWindow)
        QTest.qWait(100)

        def visual_item(parent, name):
            if parent.objectName() == name:
                return parent
            for child in parent.childItems():
                found = visual_item(child, name)
                if found is not None:
                    return found
            return None

        def click(name):
            item = visual_item(window.contentItem(), name)
            self.assertIsNotNone(item)
            point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(20)

        click("recordButton")
        self.assertFalse(controller.recording)
        controller.app = Mock(applicationState=lambda: Qt.ApplicationActive)
        controller.on_input({"candidate_assignment_hex": controller.value(0)})
        self.assertTrue(controller.confirm)
        controller.record()
        QTest.qWait(20)
        self.assertTrue(controller.recording)
        QTest.keyClick(window, Qt.Key_P, Qt.ShiftModifier)
        self.assertEqual(controller.pending, "20021300")
        click("saveButton")
        self.assertEqual(controller.ui["current"], "Shift + P")
        click("undoButton")
        self.assertEqual(controller.ui["current"], "Num 7")
        controller.clear_flash()
        QTest.qWait(200)
        output = os.environ.get("GLRA_SCREENSHOT_DIR")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-light.png")))
        window.setProperty("dark", True)
        QTest.qWait(220)
        if output:
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-dark.png")))
        click("lightingButton")
        self.assertTrue(controller.light_open)
        click("lightingMode1")
        dialog = window.findChild(QObject, "lightingDialog")
        for channel, value in (("red", 160), ("green", 32), ("blue", 240)):
            slider = visual_item(window.contentItem(), "lightingSlider" + channel)
            slider.setProperty("value", value)
            slider.moved.emit()

        controller.changed.emit()
        QTest.qWait(30)
        dialog = window.findChild(QObject, "lightingDialog")
        self.assertEqual(dialog.property("draftMode"), 1)
        self.assertEqual(dialog.property("red"), 160)
        self.assertEqual(dialog.property("green"), 32)
        self.assertEqual(dialog.property("blue"), 240)
        self.assertEqual(controller.ui["lightMode"], 4)
        self.assertEqual(controller.ui["lightColor"], -1)
        click("lightingApply")
        self.assertEqual(controller.ui["lightMode"], 1)
        self.assertEqual(
            bytes.fromhex(controller.light_value)[6:11], bytes([1, 255, 196, 221, 240])
        )
        click("lightingUndo")
        self.assertEqual(controller.ui["lightMode"], 4)
        click("lightingMode1")
        dialog.setProperty("red", 64)
        dialog.setProperty("green", 128)
        dialog.setProperty("blue", 112)
        dialog.setProperty("colorEdited", True)
        QTest.qWait(220)
        if output:
            self.assertTrue(
                window.grabWindow().save(str(Path(output) / "screenshot-lighting-dark.png"))
            )
        controller.closeLighting()
        QTest.qWait(100)
        window.setWidth(1110)
        window.setHeight(840)
        QTest.qWait(220)
        if output:
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-compact.png")))
        self.assertEqual(warnings, [])
        window.close()
        app.removeEventFilter(controller)
        del engine
