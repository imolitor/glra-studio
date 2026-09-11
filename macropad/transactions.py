"""Single-control transactions: fresh backup, bounded write, complete readback."""

from datetime import datetime, timezone
from pathlib import Path
from .storage import save, now
from .model import VISIBLE_SLOTS


def fingerprint(status):
    return tuple(
        status[k] for k in ("version", "internal_pid", "firmware", "profile_count", "layer_count")
    )


def validate_status(status):
    if (
        fingerprint(status) != (1, 0x246D, 100, 6, 1)
        or status["current_profile"] != 0
        or status["current_layer"] != 0
    ):
        raise ValueError("Writing is supported only on tested firmware 100, profile 1, layer 1.")


def snapshot(reader):
    status = reader.status()
    validate_status(status)
    tables = {}
    for p in range(6):
        x = reader.memory(8, 576, p)
        if x != reader.memory(8, 576, p):
            raise ValueError("The device changed while reading. Try again.")
        tables[str(p)] = x.hex()
    return status, tables


def changes(before, after):
    found = []
    for p, hex_data in before.items():
        old = bytes.fromhex(hex_data)
        new = bytes.fromhex(after[p])
        if len(old) != len(new):
            raise ValueError("Readback length changed")
        for offset in range(0, len(old), 4):
            if old[offset : offset + 4] != new[offset : offset + 4]:
                found.append(
                    (p, offset // 4, old[offset : offset + 4].hex(), new[offset : offset + 4].hex())
                )
    return found


def packet(slot, value):
    if slot not in VISIBLE_SLOTS or len(value) != 4:
        raise ValueError("Invalid control or assignment")
    p = bytearray(65)
    p[:9] = bytes([0, 6, 16, 7, slot * 4, 0, 0, 0, 0])
    p[9:13] = value
    return bytes(p)


class TransactionError(RuntimeError):
    def __init__(self, message, backup, slot, before, after):
        super().__init__(message)
        self.backup, self.slot, self.before, self.after = backup, slot, before, after


def write_one(reader, identity, slot, new_value, expected_old, directory, purpose="assignment"):
    if slot not in VISIBLE_SLOTS:
        raise ValueError("Unknown control")
    new_value = bytes.fromhex(new_value)
    if len(new_value) != 4:
        raise ValueError("Invalid assignment")
    if purpose not in ("restore", "calibration_restore") and (
        new_value[0] != 32 or new_value[3] != 0 or not 4 <= new_value[2] <= 115
    ):
        raise ValueError("Only a single keyboard key with modifiers can be recorded.")
    status, before = snapshot(reader)
    old = bytes.fromhex(before["0"])[slot * 4 : slot * 4 + 4].hex()
    if old != expected_old:
        raise ValueError("This assignment changed outside the app. Reload before saving.")
    if old == new_value.hex():
        return {"unchanged": True, "tables": before, "status": status}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = Path(directory) / f"{stamp}-before.json"
    backup = {
        "schema": "glra-single-control-v1",
        "created": now(),
        "device": identity,
        "status": status,
        "assignments": before,
        "slot": slot,
        "before": old,
        "after": new_value.hex(),
        "purpose": purpose,
        "scope": "Client-visible assignment windows; not a full firmware backup.",
    }
    save(path, backup)  # Must succeed before any write is attempted.
    result = {
        "created": now(),
        "backup": str(path),
        "slot": slot,
        "before": old,
        "after": new_value.hex(),
    }
    try:
        current = reader.status()
        validate_status(current)
        if fingerprint(current) != fingerprint(status):
            raise ValueError("Device state changed")
        p = packet(slot, new_value)
        reader.audit.record("single_control_write", hex=p.hex(), backup=str(path), purpose=purpose)
        n = reader.device.write(p)
        ack = bytes(reader.device.read(64, 2000))
        reader.audit.record("write_ack", hex=ack.hex())
        result["ack_hex"] = ack.hex()
        after_status, after = snapshot(reader)
        delta = changes(before, after)
        expected = [("0", slot, old, new_value.hex())]
        result.update(changes=delta, assignments_after=after)
        if delta != expected:
            raise ValueError(
                "Unexpected readback. A backup was saved; automatic writes are paused."
            )
        if n != 65 or len(ack) != 64 or ack[:3] != bytes([0xAA, 0x10, 1]) or ack[8:12] != new_value:
            raise ValueError(
                "Readback changed, but the device acknowledgement was unexpected. Review the backup."
            )
        result["verified"] = True
        save(Path(directory) / f"{stamp}-result.json", result)
        return {**result, "tables": after, "status": after_status}
    except Exception as exc:
        result["error"] = str(exc)
        save(Path(directory) / f"{stamp}-error.json", result)
        raise TransactionError(
            f"{exc}\nBackup: {path}", str(path), slot, old, new_value.hex()
        ) from exc
