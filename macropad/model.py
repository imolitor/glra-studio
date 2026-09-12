# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

"""Device layout and lossless labels for four-byte assignments."""

from .learn import usage_name

KEY_SLOTS = [0, 1, 2, 3, 7, 8, 9, 10, 14, 15, 16, 17, 21, 22, 23, 24]
ENCODER_SLOTS = [(4, 5, 6), (11, 12, 13), (18, 19, 20)]  # press, clockwise, counterclockwise
VISIBLE_SLOTS = frozenset(KEY_SLOTS + [s for group in ENCODER_SLOTS for s in group])
HARDWARE_VERIFIED = frozenset((0, 4, 5, 6))


def label(value):
    raw = bytes.fromhex(value) if isinstance(value, str) else bytes(value)
    if len(raw) != 4:
        raise ValueError("An assignment must contain four bytes")
    t, m, u, last = raw
    if t == 0 and not any(raw):
        return "Unassigned"
    if t == 0x20:
        names = {
            0x58: "Num ↵",
            0x63: "Num .",
            0x4F: "→",
            0x50: "←",
            0x51: "↓",
            0x52: "↑",
            0x28: "Enter",
            0x29: "Esc",
            0x2C: "Space",
            0x2A: "⌫",
            0x2B: "Tab",
        }
        key = (
            chr(65 + u - 4)
            if 4 <= u <= 29
            else names.get(u, usage_name(u).replace("Numpad", "Num"))
        )
        if 30 <= u <= 39:
            key = str((u - 29) % 10)
        mods = [
            name
            for mask, name in [
                (1, "Ctrl"),
                (2, "Shift"),
                (4, "⌥"),
                (8, "⌘"),
                (16, "R Ctrl"),
                (32, "R Shift"),
                (64, "R ⌥"),
                (128, "R ⌘"),
            ]
            if m & mask
        ]
        return " + ".join(mods + [key]) + (f" [{last:02x}]" if last else "")
    if t == 0x30:
        return {0xE2: "Mute", 0xE9: "Volume +", 0xEA: "Volume −"}.get(
            m + (u << 8), f"Media {m + (u << 8):04X}"
        )
    if t == 0x60:
        return f"Macro {m}"
    return f"Custom · {raw.hex(' ')}"


def control_name(slot):
    if slot in KEY_SLOTS:
        i = KEY_SLOTS.index(slot)
        return f"Key {i + 1} · row {i // 4 + 1}, column {i % 4 + 1}"
    for i, group in enumerate(ENCODER_SLOTS):
        if slot in group:
            return f"{['Upper', 'Middle', 'Lower'][i]} dial · {['press', 'right', 'left'][group.index(slot)]}"
    raise ValueError("Unknown control")


def demo_table():
    table = bytearray(576)
    keys = [
        0x5F,
        0x60,
        0x61,
        0x56,
        0x5C,
        0x5D,
        0x5E,
        0x57,
        0x59,
        0x5A,
        0x5B,
        0x54,
        0x55,
        0x62,
        0x63,
        0x58,
    ]
    for slot, usage in zip(KEY_SLOTS, keys):
        table[slot * 4 : slot * 4 + 4] = bytes([32, 0, usage, 0])
    for press, right, left in ENCODER_SLOTS:
        for slot, usage in [(press, 0xE2), (right, 0xE9), (left, 0xEA)]:
            table[slot * 4 : slot * 4 + 4] = bytes([48, usage, 0, 0])
    return bytes(table)
