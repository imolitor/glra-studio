# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

"""Bounded, passive key learning from this macropad only; never writes HID."""

import time
from contextlib import ExitStack
from pathlib import Path
from . import backend, storage

# Only decode the descriptors actually inspected on this device.
# Correct boot descriptor copied byte-for-byte from the initial registry dump.


EXTENDED_DESCRIPTOR = bytes.fromhex(
    "05010906a1018501050719e029e71500250175019508810205071900296d150025017501956e8102950175028103c005010902a10185020901a1000509190129051500250195057501810295017503810305010930093116008026ff7f75109502810609381581257f750895018106050c0a380295018106c0c0050c0901a101850319002acc02150026cc02950175108100c005010980a10185041981298315002501750195038102750595018101c00501090ca101850519c629c815002501750195018102750195078103c0"
)
BOOT_DESCRIPTOR = bytes.fromhex(
    "05010906a101050719e029e71500250195087501810295017508810395067508150026ff000507190029ff81002501950575010508190129059102950175039103c0"
)


def usage_name(usage):
    names = {
        0x28: "Enter",
        0x29: "Escape",
        0x2A: "Backspace",
        0x2B: "Tab",
        0x2C: "Space",
        0x4F: "Arrow right",
        0x50: "Arrow left",
        0x51: "Arrow down",
        0x52: "Arrow up",
        0x54: "Numpad /",
        0x55: "Numpad *",
        0x56: "Numpad -",
        0x57: "Numpad +",
        0x58: "Numpad Enter",
        0x62: "Numpad 0",
        0x63: "Numpad decimal",
    }
    if 0x59 <= usage <= 0x61:
        return f"Numpad {usage - 0x58}"
    if 4 <= usage <= 29:
        return f"Keyboard usage {chr(65 + usage - 4)} (layout-dependent)"
    if 0x3A <= usage <= 0x45:
        return f"F{usage - 0x39}"
    if 0x68 <= usage <= 0x73:
        return f"F{usage - 0x68 + 13}"
    return names.get(usage, f"HID usage 0x{usage:02x}")


def decode(raw, interface):
    """Return non-empty key states, not text interpreted by the OS layout."""
    if interface == 0:
        if len(raw) != 8:
            return None
        modifiers, usages = raw[0], sorted(set(raw[2:]) - {0})
        if any(u in (1, 2, 3) for u in usages):
            return None  # HID error/rollover; never treat it as a key.
    elif interface == 1:
        if len(raw) == 3 and raw[0] == 3:
            usage = int.from_bytes(raw[1:], "little")
            if not usage:
                return None
            return {
                "kind": "consumer",
                "usage": usage,
                "name": {0xE2: "Mute", 0xE9: "Volume up", 0xEA: "Volume down"}.get(
                    usage, f"Consumer 0x{usage:04x}"
                ),
                "candidate_assignment_hex": bytes([0x30, usage & 255, usage >> 8, 0]).hex(),
            }
        if len(raw) != 16 or raw[0] != 1:
            return None
        modifiers = raw[1]
        usages = [u for u in range(1, 110) if raw[2 + u // 8] & (1 << (u % 8))]
        if any(u in (1, 2, 3) for u in usages):
            return None
    else:
        return None
    if not usages:
        return None
    result = {
        "kind": "keyboard",
        "usages": usages,
        "names": [usage_name(u) for u in usages],
        "modifiers": modifiers,
    }
    if len(usages) == 1:
        result["candidate_assignment_hex"] = bytes([0x20, modifiers, usages[0], 0]).hex()
    return result


def matches(event, dump):
    value = event.get("candidate_assignment_hex")
    if not value:
        return []
    found = []
    for parameter, raw_hex in dump.get("assignments", {}).items():
        raw = bytes.fromhex(raw_hex)
        for offset in range(0, len(raw) - 3, 4):
            if raw[offset : offset + 4].hex() == value:
                found.append({"read_parameter": int(parameter), "raw_slot": offset // 4})
    return found


def capture(seconds, out, audit, backup=None):
    if Path(out).exists():
        raise FileExistsError(out)
    dump = storage.load(backup) if backup else None
    anchor = backend.select()  # Refuse ambiguity between two attached macropads.
    unique = {d["path"]: d for d in backend.enumerate_devices() if d["interface_number"] in (0, 1)}
    if not unique:
        raise ValueError("No keyboard interfaces found for G-LRA k16_n3")
    with ExitStack() as stack:
        devices = []
        errors = []
        for info in unique.values():
            try:
                dev = stack.enter_context(backend.open_device(info))
                raw = bytes(dev.get_report_descriptor())
                expected = {0: BOOT_DESCRIPTOR, 1: EXTENDED_DESCRIPTOR}[info["interface_number"]]
                if raw != expected:
                    raise ValueError("Keyboard descriptor differs; decoder blocked")
                devices.append((info, dev))
            except OSError as exc:
                errors.append(f"Interface {info['interface_number']}: {exc}")
        if not devices:
            raise OSError(
                "Keyboard access is blocked. Enable Input Monitoring for the launching app, then restart it. "
                + "; ".join(errors)
            )
        audit.record("learn_ready", paths=[i["path"] for i, d in devices], errors=errors)
        print("READY: Briefly press exactly one control on the macropad.", flush=True)
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for info, dev in devices:
                raw = bytes(dev.read(64, 25))
                if not raw:
                    continue
                event = decode(raw, info["interface_number"])
                audit.record("learn_input", path=info["path"], hex=raw.hex(), decoded=event)
                if not event:
                    continue
                result = {
                    "schema": "glra-macropad-key-observation-v1",
                    "created": storage.now(),
                    "device": info,
                    "vendor_device": anchor,
                    "raw_hex": raw.hex(),
                    "event": event,
                    "configuration_written": False,
                    "output_reports_sent": 0,
                    "assignment_matches": matches(event, dump) if dump else [],
                    "mapping_verified": False,
                    "note": "Matches are raw dump positions, not proven physical indices. Backup may be stale.",
                }
                storage.save(out, result)
                return result
    raise TimeoutError("No key was detected before the timeout. Nothing was changed.")
