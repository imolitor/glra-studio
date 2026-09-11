"""Tested lighting modes with private backups and exact readback checks."""

from datetime import datetime, timezone
from pathlib import Path
from . import storage
from .transactions import snapshot

MODES = {0: "Off", 1: "Steady", 2: "Breathing", 4: "Rainbow wave"}
# Observed settings on firmware 100; used when switching on from normalized Off.
DEFAULT = bytes.fromhex("0100040403030008ffffff")


def validate(value):
    if len(value) != 11 or value[0:2] != b"\x01\x00" or value[2] not in MODES:
        raise ValueError("This lighting configuration is not supported yet.")
    return value


def read(reader):
    raw = reader.query(10)
    if raw[2] != 11:
        raise ValueError("Unexpected lighting response size.")
    return validate(raw[5:16])


def for_mode(current, mode):
    validate(current)
    if mode not in MODES:
        raise ValueError("Unknown lighting mode.")
    if mode == 0:
        return bytes([1]) + bytes(10)
    value = bytearray(DEFAULT if current[2] == 0 else current)
    value[2] = mode
    return bytes(value)


def color_index(value):
    validate(value)
    if value[6:8] == bytes([1, 255]) and value[9:11] == bytes([255, 255]):
        return {0: 0, 85: 1, 170: 2}.get(value[8], -1)
    return -1


def for_selection(current, mode, color=-1):
    if color not in (-1, 0, 1, 2):
        raise ValueError("Unknown fixed color.")
    value = bytearray(for_mode(current, mode))
    if mode == 1 and color >= 0:
        value[6:11] = bytes([1, 255, (0, 85, 170)[color], 255, 255])
    return bytes(value)


def write(reader, identity, value, expected, directory):
    value = validate(value)
    status, tables = snapshot(reader)
    before = read(reader)
    if before != read(reader) or before.hex() != expected:
        raise ValueError("Lighting changed outside the app. Reopen Lighting and try again.")
    if value == before:
        return {"before": before.hex(), "after": before.hex(), "unchanged": True}
    rgb = reader.memory(19, 432)
    if rgb != reader.memory(19, 432):
        raise ValueError("RGB data changed while reading.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = Path(directory) / f"{stamp}-lighting-before.json"
    storage.save(
        path,
        {
            "schema": "glra-lighting-v1",
            "created": storage.now(),
            "device": identity,
            "status": status,
            "assignments": tables,
            "rgb": rgb.hex(),
            "before": before.hex(),
            "after": value.hex(),
        },
    )
    result = {"before": before.hex(), "after": value.hex(), "backup": str(path)}
    try:
        packet = bytes([0, 6, 11, 11, 0, 0]) + value + bytes(48)
        reader.audit.record("lighting_write", hex=packet.hex(), backup=str(path))
        n = reader.device.write(packet)
        ack = bytes(reader.device.read(64, 2000))
        reader.audit.record("lighting_ack", hex=ack.hex())
        result["ack_hex"] = ack.hex()
        after = read(reader)
        if after != read(reader) or after != value:
            raise ValueError("Lighting readback did not match. Further writes are paused.")
        if n != 65 or len(ack) != 64 or ack[:3] != b"\xaa\x0b\x01" or ack[5:16] != value:
            raise ValueError("Unexpected lighting acknowledgement.")
        _, after_tables = snapshot(reader)
        if after_tables != tables or reader.memory(19, 432) != rgb:
            raise ValueError("Assignments or RGB data changed unexpectedly.")
        result["verified"] = True
        storage.save(Path(directory) / f"{stamp}-lighting-result.json", result)
        return result
    except Exception as exc:
        result["error"] = str(exc)
        storage.save(Path(directory) / f"{stamp}-lighting-error.json", result)
        raise RuntimeError(f"{exc}\nLighting backup: {path}") from exc
