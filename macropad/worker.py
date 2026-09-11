"""Keep HIDAPI and all device transactions on one worker thread."""

import queue
import time
from contextlib import ExitStack
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from . import backend, storage, lighting
from .protocol import Reader
from .learn import decode, BOOT_DESCRIPTOR, EXTENDED_DESCRIPTOR
from .model import VISIBLE_SLOTS, HARDWARE_VERIFIED
from .transactions import write_one, validate_status


class DeviceWorker(QThread):
    state = Signal(object)
    input = Signal(object)
    completed = Signal(object)
    fault = Signal(str)
    busy = Signal(bool)

    def __init__(self, directory):
        super().__init__()
        self.directory = Path(directory)
        self.commands = queue.Queue()
        self.stopping = False
        self.stack = None
        self.reader = None
        self.monitors = []
        self.identity = None
        self.last_event = (None, 0)
        self.calibration = None
        self.pending = self.directory / "pending-calibration.json"
        self.verified = set(HARDWARE_VERIFIED)
        self.light_undo = None
        self.undo = None
        self.write_blocked = False

    def submit(self, command, *args):
        self.commands.put((command, args))

    def disconnect(self):
        if self.stack:
            self.stack.close()
        self.stack = None
        self.reader = None
        self.monitors = []
        self.identity = None
        self.light_undo = None
        self.undo = None

    def publish(self):
        status = self.reader.status()
        table = self.reader.memory(8, 112, status["current_profile"])
        writable = True
        try:
            validate_status(status)
        except ValueError:
            writable = False
        self.state.emit(
            {
                "connected": True,
                "identity": self.identity,
                "status": status,
                "table": table.hex(),
                "writable": writable and not self.write_blocked,
                "input_available": bool(self.monitors),
                "verified": list(self.verified),
                "recovery": self.pending.exists(),
            }
        )

    def connect_device(self):
        rows = backend.enumerate_devices(True)
        vendors = {
            d["path"]: d
            for d in rows
            if d["vendor_id"] == backend.VID
            and d["product_id"] == backend.PID
            and d["usage_page"] == 0xFF00
            and d["usage"] == 2
        }
        if len(vendors) != 1:
            self.disconnect()
            related = sorted(
                set(
                    f"{d.get('manufacturer_string', '')} {d.get('product_string', '')} ({d['vendor_id']:04x}:{d['product_id']:04x})"
                    for d in rows
                    if d["vendor_id"] in (0x36AE, 0x0816)
                )
            )
            self.state.emit(
                {
                    "connected": False,
                    "reason": "Connect one supported pad"
                    if not vendors
                    else "Connect only one G-LRA pad",
                    "related": related,
                    "recovery": self.pending.exists(),
                }
            )
            return
        identity = next(iter(vendors.values()))
        if self.reader and identity["path"] == self.identity["path"]:
            if not self.calibration:
                self.publish()
            return
        self.disconnect()
        self.stack = ExitStack()
        try:
            device = self.stack.enter_context(backend.open_device(identity))
            self.reader = Reader(device, self.audit)
            self.identity = identity
            self.verified = set(HARDWARE_VERIFIED)
            paths = {
                d["path"]: d
                for d in rows
                if (d["vendor_id"], d["product_id"]) == (backend.VID, backend.PID)
                and d["interface_number"] in (0, 1)
            }
            for info in paths.values():
                try:
                    h = self.stack.enter_context(backend.open_device(info))
                    expected = {0: BOOT_DESCRIPTOR, 1: EXTENDED_DESCRIPTOR}[
                        info["interface_number"]
                    ]
                    if bytes(h.get_report_descriptor()) == expected:
                        self.monitors.append((info, h))
                except OSError:
                    pass
            self.publish()
        except Exception:
            self.disconnect()
            raise

    def restore_pending(self):
        if not self.reader:
            raise ValueError("Reconnect the pad to restore the temporary test.")
        p = storage.load(self.pending)
        if any(
            p["device"].get(k) != self.identity.get(k)
            for k in ("vendor_id", "product_id", "serial_number")
        ):
            raise ValueError("The pending test belongs to another device.")
        validate_status(self.reader.status())
        table = self.reader.memory(8, 112, 0)
        slot = p["slot"]
        value = table[slot * 4 : slot * 4 + 4].hex()
        if value == p["marker"]:
            write_one(
                self.reader,
                self.identity,
                slot,
                p["before"],
                p["marker"],
                self.directory / "backups",
                "calibration_restore",
            )
        elif value != p["before"]:
            raise ValueError("The test control changed externally. Restore was not attempted.")
        self.pending.unlink()
        self.calibration = None

    def handle(self, command, args):
        if command == "stop":
            if self.pending.exists() and self.reader:
                try:
                    self.restore_pending()
                except Exception as exc:
                    self.fault.emit(str(exc))
            self.stopping = True
            return
        if command == "refresh":
            if self.reader:
                self.publish()
            else:
                self.connect_device()
            return
        if not self.reader:
            raise ValueError("No supported device is connected.")
        if command == "recover":
            self.restore_pending()
            self.publish()
            self.completed.emit({"kind": "recovered"})
            return
        if self.pending.exists():
            raise ValueError("Finish or restore the pending control test first.")
        if self.write_blocked and command in (
            "save",
            "undo",
            "calibrate",
            "lighting_save",
            "lighting_restore",
        ):
            raise ValueError(
                "Writing was paused after an error. Review the backup and restart the app."
            )
        if command == "lighting_read":
            validate_status(self.reader.status())
            value = lighting.read(self.reader)
            self.completed.emit(
                {
                    "kind": "lighting_loaded",
                    "value": value.hex(),
                    "canUndo": self.light_undo is not None,
                }
            )
            return
        if command in ("lighting_save", "lighting_restore"):
            if command == "lighting_restore":
                if not self.light_undo:
                    raise ValueError("No lighting change to undo in this session.")
                old, expected = self.light_undo
                value = bytes.fromhex(old)
            else:
                mode, expected = args
                value = lighting.for_mode(bytes.fromhex(expected), mode)
            result = lighting.write(
                self.reader, self.identity, value, expected, self.directory / "backups"
            )
            if command == "lighting_restore":
                self.light_undo = None
            elif not result.get("unchanged"):
                self.light_undo = (result["before"], result["after"])
            self.completed.emit(
                {
                    "kind": "lighting_saved",
                    "value": result["after"],
                    "canUndo": self.light_undo is not None,
                }
            )
            return
        if command == "save":
            slot, value, expected = args
            if slot not in self.verified:
                raise ValueError("Verify this physical control before saving.")
            result = write_one(
                self.reader, self.identity, slot, value, expected, self.directory / "backups"
            )
            if not result.get("unchanged"):
                self.undo = (slot, result["before"], result["after"])
            self.publish()
            self.completed.emit({"kind": "saved", "result": result})
            return
        if command == "undo":
            if not self.undo:
                raise ValueError("No change to undo in this session.")
            slot, old, new = self.undo
            result = write_one(
                self.reader, self.identity, slot, old, new, self.directory / "backups", "restore"
            )
            self.undo = None
            self.publish()
            self.completed.emit({"kind": "undone", "result": result})
            return
        if command == "calibrate":
            slot = args[0]
            if slot not in VISIBLE_SLOTS:
                raise ValueError("Unknown control")
            if not self.monitors:
                raise ValueError("Enable Input Monitoring and restart the application first.")
            status = self.reader.status()
            validate_status(status)
            table = self.reader.memory(8, 112, 0)
            used = {table[i : i + 4].hex() for i in range(0, len(table), 4)}
            marker = next(
                (
                    bytes([32, 0, u, 0]).hex()
                    for u in range(115, 103, -1)
                    if bytes([32, 0, u, 0]).hex() not in used
                ),
                None,
            )
            if not marker:
                raise ValueError("No unused test key is available.")
            old = table[slot * 4 : slot * 4 + 4].hex()
            storage.save(
                self.pending,
                {
                    "device": self.identity,
                    "slot": slot,
                    "before": old,
                    "marker": marker,
                    "created": storage.now(),
                },
            )
            try:
                write_one(
                    self.reader,
                    self.identity,
                    slot,
                    marker,
                    old,
                    self.directory / "backups",
                    "calibration",
                )
            except Exception:
                # The pending journal remains even if the USB write was uncertain.
                raise
            self.calibration = {"slot": slot, "marker": marker, "deadline": time.monotonic() + 90}
            self.completed.emit({"kind": "calibrating", "slot": slot})
            return
        raise ValueError("Unknown device operation")

    def run(self):
        self.audit = storage.Audit(self.directory / "logs")
        next_scan = 0
        try:
            while not self.stopping:
                try:
                    command, args = self.commands.get(timeout=0.015)
                except queue.Empty:
                    command = None
                if command:
                    self.busy.emit(True)
                    try:
                        self.handle(command, args)
                    except Exception as exc:
                        if command in (
                            "save",
                            "undo",
                            "calibrate",
                            "lighting_save",
                            "lighting_restore",
                        ):
                            self.write_blocked = True
                            self.completed.emit({"kind": "writes_paused"})
                        self.audit.record("operation_error", message=str(exc))
                        self.fault.emit(str(exc))
                        if self.pending.exists():
                            self.completed.emit({"kind": "recovery_needed"})
                    finally:
                        self.busy.emit(False)
                if self.stopping:
                    break
                if time.monotonic() >= next_scan:
                    next_scan = time.monotonic() + 2
                    try:
                        self.connect_device()
                    except Exception as exc:
                        self.state.emit(
                            {
                                "connected": False,
                                "reason": str(exc),
                                "recovery": self.pending.exists(),
                            }
                        )
                if self.calibration and time.monotonic() > self.calibration["deadline"]:
                    self.busy.emit(True)
                    try:
                        self.restore_pending()
                        self.publish()
                        self.completed.emit({"kind": "recovered"})
                        self.fault.emit(
                            "Control test timed out. The previous assignment was restored."
                        )
                    except Exception as exc:
                        self.fault.emit(str(exc))
                        self.completed.emit({"kind": "recovery_needed"})
                    finally:
                        self.calibration = None
                        self.busy.emit(False)
                for info, device in list(self.monitors):
                    try:
                        raw = bytes(device.read(64, 1))
                        if not raw:
                            continue
                        event = decode(raw, info["interface_number"])
                        if not event:
                            continue
                        value = event.get("candidate_assignment_hex")
                        if (
                            value == self.last_event[0]
                            and time.monotonic() - self.last_event[1] < 0.25
                        ):
                            continue
                        self.last_event = (value, time.monotonic())
                        if self.calibration and value == self.calibration["marker"]:
                            slot = self.calibration["slot"]
                            self.busy.emit(True)
                            try:
                                self.restore_pending()
                                self.verified.add(slot)
                                self.publish()
                                self.completed.emit({"kind": "calibrated", "slot": slot})
                            finally:
                                self.busy.emit(False)
                        else:
                            self.input.emit(event)
                    except Exception as exc:
                        self.audit.record("input_disconnect", message=str(exc))
                        self.disconnect()
                        self.state.emit(
                            {
                                "connected": False,
                                "reason": "Pad disconnected. Reconnect it to continue.",
                                "recovery": self.pending.exists(),
                            }
                        )
                        break
        finally:
            self.disconnect()
            self.audit.close()
