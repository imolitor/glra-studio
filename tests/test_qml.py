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

        def click(name):
            item = window.findChild(QObject, name)
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
        output = os.environ.get("GLRA_SCREENSHOT_DIR")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-light.png")))
        window.setProperty("dark", True)
        QTest.qWait(220)
        if output:
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-dark.png")))
        window.setWidth(1110)
        window.setHeight(840)
        QTest.qWait(220)
        if output:
            self.assertTrue(window.grabWindow().save(str(Path(output) / "screenshot-compact.png")))
        self.assertEqual(warnings, [])
        window.close()
        app.removeEventFilter(controller)
        del engine
