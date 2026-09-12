# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

"""Allowlisted READ requests recovered from the public SDCX web client.

These reads need USB Output reports. No configuration-changing opcode is exposed.
All returned bytes remain available in the audit log, including ignored packets.
"""

import time

VENDOR_DESCRIPTOR = bytes.fromhex("0600ff0902a10119002aff00150026ff0075089540810019002aff009100c0")


def read_packet(command, offset=0, length=0, profile=0):
    packet = bytearray(65)  # HIDAPI report ID zero + 64-byte unnumbered payload
    packet[1] = 6
    if command == 5:
        if offset or length or profile:
            raise ValueError("Status request has no arguments")
        packet[2] = 5
    elif command == 8:
        if length != 56 or offset % 56 or not 0 <= offset < 576 or not 0 <= profile < 6:
            raise ValueError("Invalid assignment read range")
        packet[2:8] = bytes([8, 58, offset & 255, offset >> 8, 0, profile])
    elif command in (12, 65):
        maximum = {12: 4096, 65: 128}[command]
        if (
            profile
            or not 1 <= length <= 56
            or not 0 <= offset < maximum
            or offset + length > maximum
        ):
            raise ValueError("Invalid read range")
        packet[2:6] = bytes([command, length, offset & 255, offset >> 8])
    elif command == 19:
        if profile or length != 56 or offset % 56 or not 0 <= offset < 432:
            raise ValueError("Invalid RGB read range")
        packet[2:6] = bytes([19, 58, offset & 255, offset >> 8])
    elif command == 10:
        if offset or length or profile:
            raise ValueError("Light read has no arguments")
        packet[2] = 10
    else:
        raise PermissionError(f"Opcode {command:#x} is not an allowlisted read")
    return bytes(packet)


class Reader:
    def __init__(self, device, audit, timeout=2.0):
        self.device, self.audit, self.timeout = device, audit, timeout
        descriptor = bytes(device.get_report_descriptor())
        if descriptor != VENDOR_DESCRIPTOR:
            raise ValueError("Vendor descriptor changed; protocol access blocked")

    def query(self, command, offset=0, length=0, profile=0):
        packet = read_packet(command, offset, length, profile)
        # Drop stale responses with a hard bound: never wait forever on noise.
        for _ in range(32):
            stale = bytes(self.device.read(64, 1))
            if not stale:
                break
            self.audit.record("input_stale", hex=stale.hex())
        else:
            raise RuntimeError("Input queue will not drain")
        self.audit.record("output_read_request", hex=packet.hex(), includes_report_id=True)
        n = self.device.write(packet)
        if n != len(packet):
            raise IOError(f"Short USB write: {n}/{len(packet)}")
        deadline = time.monotonic() + self.timeout
        expected = 7 if command == 8 else command
        while time.monotonic() < deadline:
            response = bytes(
                self.device.read(64, max(1, min(100, int((deadline - time.monotonic()) * 1000))))
            )
            if not response:
                continue
            self.audit.record("input", hex=response.hex(), command=command)
            if len(response) != 64 or response[:2] != bytes([0xAA, expected]):
                self.audit.record("input_ignored", reason="Length or response command mismatch")
                continue
            if command in (8, 12, 19, 65):
                if int.from_bytes(response[3:5], "little") != offset:
                    self.audit.record("input_ignored", reason="Offset mismatch")
                    continue
                expected_length = 58 if command in (8, 19) else length
                if response[2] != expected_length:
                    raise ValueError("Unexpected response length field")
            return response
        raise TimeoutError(f"No matching response for read {command:#x}, offset {offset}")

    def status(self):
        raw = self.query(5)
        if raw[2] < 14:
            raise ValueError("Status payload too short")
        b = raw[5:]
        result = dict(
            version=int.from_bytes(b[0:2], "little"),
            internal_pid=int.from_bytes(b[2:4], "little"),
            firmware=int.from_bytes(b[4:6], "little"),
            work_mode=b[6],
            link_status=b[7],
            battery=b[8],
            charging=b[9],
            profile_count=b[10],
            current_profile=b[11],
            layer_count=b[12],
            current_layer=b[13],
            raw_hex=raw.hex(),
        )
        if not 1 <= result["profile_count"] <= 6 or result["layer_count"] != 1:
            raise ValueError("Unverified profile/layer dimensions; backup blocked")
        return result

    def memory(self, command, size, profile=0):
        chunks = []
        for offset in range(0, size, 56):
            length = 56 if command in (8, 19) else min(56, size - offset)
            raw = self.query(command, offset, length, profile)
            chunks.append(raw[8 : 8 + min(56, size - offset)])
        return b"".join(chunks)

    def backup(self):
        before = self.status()
        # 576-byte table capacity is from getKeyInfosData in the client.
        # Physical slot labels are deliberately not inferred from sibling layouts.
        assignments = {}
        for profile in range(before["profile_count"]):
            first = self.memory(8, 576, profile)
            second = self.memory(8, 576, profile)
            if first != second:
                raise ValueError(f"Profile {profile} changed between reads")
            assignments[str(profile)] = first.hex()
        extra = {}
        for name, command, size in [("macro", 12, 4096), ("url", 65, 128), ("rgb", 19, 432)]:
            try:
                first = self.memory(command, size)
                second = self.memory(command, size)
                if first != second:
                    raise ValueError("Data changed between reads")
                extra[name] = {"hex": first.hex(), "double_read_equal": True}
            except (OSError, ValueError, TimeoutError) as exc:
                extra[name] = {"error": str(exc)}
        try:
            extra["light"] = {"raw_hex": self.query(10).hex()}
        except (OSError, ValueError, TimeoutError) as exc:
            extra["light"] = {"error": str(exc)}
        after = self.status()
        for field in (
            "version",
            "internal_pid",
            "firmware",
            "profile_count",
            "current_profile",
            "layer_count",
            "current_layer",
        ):
            if before[field] != after[field]:
                raise ValueError(f"Status changed during backup: {field}")
        return {
            "status": before,
            "assignments": assignments,
            "extra": extra,
            "assignment_double_read_equal": True,
            "restorable": False,
            "limitations": [
                "Physical slot mapping and restore are not verified.",
                "576-byte windows may overlap logical profiles; repeated 28-slot patterns observed.",
                "Profile selector semantics are source-derived, not independently proven.",
                "Dump covers client-visible regions, not full flash/EEPROM.",
            ],
        }


def decode_assignments(hex_data):
    raw = bytes.fromhex(hex_data)
    if len(raw) % 4:
        raise ValueError("Assignment table length must be divisible by four")
    rows = []
    for slot in range(len(raw) // 4):
        t, c1, c2, c3 = raw[4 * slot : 4 * slot + 4]
        row = {
            "slot": slot,
            "type": t,
            "code1": c1,
            "code2": c2,
            "code3": c3,
            "raw_hex": raw[4 * slot : 4 * slot + 4].hex(),
        }
        if t == 0x20:
            row["keyboard"] = {"modifier_mask": c1, "hid_usage": c2, "reserved": c3}
        rows.append(row)
    return rows


def write_plan(dump, profile, slot, usage, modifiers):
    """Offline only. No transport reference exists in this function."""
    if not 0 <= slot < 144 or not 0 <= usage <= 255 or not 0 <= modifiers <= 255:
        raise ValueError("Slot or HID byte out of range")
    if not dump.get("assignment_double_read_equal"):
        raise ValueError("A verified assignment dump is required")
    old = decode_assignments(dump["assignments"][str(profile)])[slot]
    packet = bytearray(65)
    offset = slot * 4
    packet[1:9] = bytes([6, 16, 7, offset & 255, offset >> 8, 0, profile, 0])
    packet[9:13] = bytes([0x20, modifiers, usage, 0])
    return {
        "enabled": False,
        "reason": "Physical mapping, ACK and restore not verified on this variant",
        "profile": profile,
        "slot": slot,
        "before": old["raw_hex"],
        "after": bytes([0x20, modifiers, usage, 0]).hex(),
        "candidate_hidapi_output_hex": packet.hex(),
        "sent": False,
    }
