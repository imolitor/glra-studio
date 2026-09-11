"""Qt Quick application bridge and focused shortcut recorder."""

import argparse
import os
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Property, Signal, Slot, QEvent, QTimer, QUrl, QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QDesktopServices
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from .model import (
    KEY_SLOTS,
    ENCODER_SLOTS,
    HARDWARE_VERIFIED,
    VISIBLE_SLOTS,
    label,
    control_name,
    demo_table,
)
from .shortcuts import encode
from .worker import DeviceWorker


class Controller(QObject):
    changed = Signal()

    def __init__(self, app, demo=False):
        super().__init__()
        self.app = app
        self.demo = demo
        self.connected = demo
        self.writable = demo
        self.table = demo_table() if demo else bytes(112)
        self.selected = 0
        self.pending = ""
        self.recording = False
        self.busy = False
        self.confirm = False
        self.calibrating = False
        self.recovery = False
        self.verified = set(VISIBLE_SLOTS) if demo else set(HARDWARE_VERIFIED)
        self.message = (
            "Explore the controls. Demo changes stay in memory."
            if demo
            else "Looking for your macropad…"
        )
        self.error = ""
        self.input_available = demo
        self.flash = -1
        self.profile = 1
        self.related = []
        self.canUndo = False
        self.demoUndo = None
        self.worker = None
        self.directory = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        self.flashTimer = QTimer(self)
        self.flashTimer.setSingleShot(True)
        self.flashTimer.timeout.connect(self.clear_flash)
        app.installEventFilter(self)
        if not demo:
            self.worker = DeviceWorker(self.directory)
            self.worker.state.connect(self.on_state)
            self.worker.input.connect(self.on_input)
            self.worker.completed.connect(self.on_complete)
            self.worker.fault.connect(self.on_fault)
            self.worker.busy.connect(self.on_busy)
            self.worker.start()

    def value(self, slot):
        return self.table[slot * 4 : slot * 4 + 4].hex()

    def card(self, slot):
        return {
            "slot": slot,
            "label": label(self.value(slot)) if self.connected else "—",
            "verified": slot in self.verified,
            "selected": slot == self.selected,
            "active": slot == self.flash,
        }

    @Property("QVariantMap", notify=changed)
    def ui(self):
        return {
            "demo": self.demo,
            "connected": self.connected,
            "writable": self.writable,
            "keys": [dict(self.card(s), number=i + 1) for i, s in enumerate(KEY_SLOTS)],
            "dials": [
                {
                    "number": i + 1,
                    "name": ["Upper dial", "Middle dial", "Lower dial"][i],
                    "press": self.card(press),
                    "right": self.card(right),
                    "left": self.card(left),
                }
                for i, (press, right, left) in enumerate(ENCODER_SLOTS)
            ],
            "selected": self.selected,
            "selectedName": control_name(self.selected),
            "current": label(self.value(self.selected)) if self.connected else "No device",
            "pending": label(self.pending) if self.pending else "",
            "recording": self.recording,
            "busy": self.busy,
            "confirm": self.confirm,
            "calibrating": self.calibrating,
            "recovery": self.recovery,
            "verified": self.selected in self.verified,
            "message": self.message,
            "error": self.error,
            "inputAvailable": self.input_available,
            "profile": self.profile,
            "related": "; ".join(self.related),
            "canUndo": self.canUndo,
            "canSave": bool(
                self.pending
                and self.connected
                and self.writable
                and self.selected in self.verified
                and not self.busy
                and not self.recovery
                and not self.calibrating
            ),
        }

    @Slot(int)
    def select(self, slot):
        if slot not in VISIBLE_SLOTS or self.busy or self.calibrating:
            return
        self.selected = slot
        self.pending = ""
        self.recording = False
        self.error = ""
        self.changed.emit()

    @Slot()
    def record(self):
        if not self.connected or self.busy or self.calibrating or self.recovery:
            return
        self.confirm = False
        self.recording = True
        self.pending = ""
        self.error = ""
        self.message = "Press a key or shortcut on your normal keyboard. Escape cancels."
        self.changed.emit()

    @Slot()
    def cancel(self):
        self.confirm = False
        self.recording = False
        self.pending = ""
        self.changed.emit()

    def eventFilter(self, obj, event):
        if self.recording and event.type() in (
            QEvent.KeyPress,
            QEvent.KeyRelease,
            QEvent.ShortcutOverride,
        ):
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
                return True
            if event.type() == QEvent.KeyRelease:
                return True
            if event.key() == Qt.Key_Escape:
                self.cancel()
                return True
            try:
                value = encode(event)
                if value:
                    self.pending = value
                    self.recording = False
                    self.message = "Shortcut captured. Review it, then save to the pad."
                    self.changed.emit()
            except ValueError as exc:
                self.on_fault(str(exc))
            return True
        if event.type() == QEvent.ApplicationDeactivate and self.recording:
            self.cancel()
        return super().eventFilter(obj, event)

    @Slot()
    def save(self):
        if not self.ui["canSave"]:
            return
        if self.demo:
            old = self.value(self.selected)
            table = bytearray(self.table)
            table[self.selected * 4 : self.selected * 4 + 4] = bytes.fromhex(self.pending)
            self.demoUndo = (self.selected, old)
            self.table = bytes(table)
            self.pending = ""
            self.canUndo = True
            self.message = "Demo assignment updated. No device was written."
            self.changed.emit()
        else:
            self.busy = True
            self.changed.emit()
            self.worker.submit("save", self.selected, self.pending, self.value(self.selected))

    @Slot()
    def undo(self):
        if self.busy or self.calibrating or self.recovery:
            return
        if self.demo and self.demoUndo:
            slot, old = self.demoUndo
            table = bytearray(self.table)
            table[slot * 4 : slot * 4 + 4] = bytes.fromhex(old)
            self.table = bytes(table)
            self.demoUndo = None
            self.canUndo = False
            self.message = "Demo change undone. No device was written."
            self.changed.emit()
        elif self.worker:
            self.busy = True
            self.changed.emit()
            self.worker.submit("undo")

    @Slot()
    def refresh(self):
        if self.worker and not self.busy and not self.calibrating:
            self.worker.submit("refresh")

    @Slot()
    def verifyControl(self):
        if self.busy or not self.connected or self.recovery:
            return
        if self.demo:
            self.verified.add(self.selected)
            self.changed.emit()
            return
        self.error = ""
        self.recording = False
        self.busy = True
        self.changed.emit()
        self.worker.submit("calibrate", self.selected)

    @Slot()
    def recover(self):
        if self.worker and not self.busy:
            self.busy = True
            self.changed.emit()
            self.worker.submit("recover")

    @Slot()
    def openBackups(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory)))

    @Slot()
    def openHelp(self):
        QDesktopServices.openUrl(QUrl("https://github.com/imolitor/glra-studio#readme"))

    @Slot()
    def clear_flash(self):
        self.flash = -1
        self.changed.emit()

    @Slot(object)
    def on_state(self, state):
        was_connected = self.connected
        self.connected = state.get("connected", False)
        self.recovery = state.get("recovery", False)
        if self.connected:
            self.table = bytes.fromhex(state["table"])
            self.writable = state["writable"]
            self.input_available = state["input_available"]
            self.profile = state["status"]["current_profile"] + 1
            self.verified = set(state["verified"])
            self.related = []
            if not was_connected:
                self.message = "Connected. Press a control on your pad or select it below."
        else:
            self.writable = False
            self.input_available = False
            self.related = state.get("related", [])
            self.message = state.get("reason", "Pad disconnected.")
            if self.related:
                self.message += (
                    " · Detected: " + "; ".join(self.related) + " — not enabled for writing."
                )
            self.pending = ""
            self.recording = False
            self.confirm = False
            self.canUndo = False
            self.calibrating = False
        self.changed.emit()

    @Slot(object)
    def on_input(self, event):
        if (
            self.recording
            or self.busy
            or self.calibrating
            or self.confirm
            or self.pending
            or self.recovery
        ):
            return
        if self.app.applicationState() != Qt.ApplicationActive:
            return
        value = event.get("candidate_assignment_hex")
        candidates = [s for s in VISIBLE_SLOTS if self.value(s) == value]
        if len(candidates) == 1:
            self.selected = candidates[0]
            self.flash = self.selected
            self.confirm = True
            self.message = "Control detected. Would you like to change its assignment?"
            self.flashTimer.start(650)
        else:
            self.message = (
                "Several controls send this same shortcut. Select the physical control on the pad."
            )
        self.changed.emit()

    @Slot(bool)
    def on_busy(self, busy):
        self.busy = busy
        self.changed.emit()

    @Slot(str)
    def on_fault(self, message):
        self.error = message
        self.recording = False
        self.changed.emit()

    @Slot(object)
    def on_complete(self, result):
        kind = result["kind"]
        if kind in ("saved", "undone", "recovered", "calibrated"):
            self.error = ""
        if kind == "writes_paused":
            self.writable = False
        if kind == "saved":
            self.pending = ""
            self.canUndo = not result["result"].get("unchanged", False)
            self.message = "Saved to your pad. Backup and readback verified."
        elif kind == "undone":
            self.canUndo = False
            self.message = "Previous assignment restored and verified."
        elif kind == "calibrating":
            self.calibrating = True
            self.message = (
                "Test active: operate ONLY "
                + control_name(result["slot"])
                + ". The old assignment will be restored automatically."
            )
        elif kind == "calibrated":
            self.calibrating = False
            self.message = "Physical control verified. Its original assignment has been restored."
        elif kind == "recovered":
            self.calibrating = False
            self.recovery = False
            self.message = "Temporary assignment restored."
        elif kind == "recovery_needed":
            self.calibrating = False
            self.recovery = True
        self.changed.emit()

    def shutdown(self):
        if self.worker:
            self.worker.submit("stop")
            self.worker.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description="GLRA Studio — a local macropad configurator")
    parser.add_argument("--demo", action="store_true", help="Run without any HID access")
    parser.add_argument("--screenshot", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("GLRA Studio")
    app.setOrganizationName("GLRA Studio")
    app.setOrganizationDomain("glra-studio.local")
    app.setApplicationDisplayName("GLRA Studio")
    if not args.demo:
        # HIDAPI's macOS manager must outlive the worker run loop.
        import hid  # noqa: F401 — initializes the manager on the main run loop
    controller = Controller(app, args.demo)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("studio", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    if not engine.rootObjects():
        controller.shutdown()
        return 1
    app.aboutToQuit.connect(controller.shutdown)
    if args.screenshot:
        window: QQuickWindow = engine.rootObjects()[0]

        def capture():
            try:
                if not window.grabWindow().save(str(Path(args.screenshot).resolve())):
                    raise RuntimeError("Could not save screenshot")
            finally:
                app.quit()

        QTimer.singleShot(1200, capture)
    elif args.smoke_test:
        QTimer.singleShot(1500, app.quit)
    result = app.exec()
    del engine
    return result


if __name__ == "__main__":
    raise SystemExit(main())
