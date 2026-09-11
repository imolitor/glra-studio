"""Convert focused Qt key events to USB keyboard usages."""

import sys
from PySide6.QtCore import Qt

# macOS virtual key codes represent physical keys, including non-US layouts.
MAC_USAGES = {
    0: 4,
    1: 22,
    2: 7,
    3: 9,
    4: 11,
    5: 10,
    6: 29,
    7: 27,
    8: 6,
    9: 25,
    11: 5,
    12: 20,
    13: 26,
    14: 8,
    15: 21,
    16: 28,
    17: 23,
    18: 30,
    19: 31,
    20: 32,
    21: 33,
    22: 35,
    23: 34,
    24: 46,
    25: 38,
    26: 36,
    27: 45,
    28: 37,
    29: 39,
    30: 48,
    31: 18,
    32: 24,
    33: 47,
    34: 12,
    35: 19,
    36: 40,
    37: 15,
    38: 13,
    39: 52,
    40: 14,
    41: 51,
    42: 49,
    43: 54,
    44: 56,
    45: 17,
    46: 16,
    47: 55,
    48: 43,
    49: 44,
    50: 53,
    51: 42,
    53: 41,
    65: 99,
    67: 85,
    69: 87,
    71: 83,
    75: 84,
    76: 88,
    78: 86,
    81: 103,
    82: 98,
    83: 89,
    84: 90,
    85: 91,
    86: 92,
    87: 93,
    88: 94,
    89: 95,
    91: 96,
    92: 97,
    96: 62,
    97: 63,
    98: 64,
    99: 60,
    100: 65,
    101: 66,
    103: 68,
    105: 104,
    106: 107,
    107: 105,
    109: 67,
    111: 69,
    113: 106,
    114: 73,
    115: 74,
    116: 75,
    117: 76,
    118: 61,
    119: 77,
    120: 59,
    121: 78,
    122: 58,
    123: 80,
    124: 79,
    125: 81,
    126: 82,
}


def encode(event):
    if event.isAutoRepeat():
        return None
    key = event.key()
    mods = event.modifiers()
    if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_CapsLock):
        return None
    usage = None
    if sys.platform == "darwin":
        usage = MAC_USAGES.get(event.nativeVirtualKey())
        # Synthetic tests have no native fields; their logical key is explicit.
        if not event.nativeVirtualKey() and key != Qt.Key_A:
            usage = None
    if usage is None:
        if Qt.Key_A <= key <= Qt.Key_Z:
            usage = 4 + key - Qt.Key_A
        elif Qt.Key_1 <= key <= Qt.Key_9:
            usage = 30 + key - Qt.Key_1
        elif key == Qt.Key_0:
            usage = 39
        elif Qt.Key_F1 <= key <= Qt.Key_F12:
            usage = 58 + key - Qt.Key_F1
        elif Qt.Key_F13 <= key <= Qt.Key_F24:
            usage = 104 + key - Qt.Key_F13
        else:
            usage = {
                Qt.Key_Return: 40,
                Qt.Key_Enter: 88,
                Qt.Key_Escape: 41,
                Qt.Key_Backspace: 42,
                Qt.Key_Tab: 43,
                Qt.Key_Space: 44,
                Qt.Key_Right: 79,
                Qt.Key_Left: 80,
                Qt.Key_Down: 81,
                Qt.Key_Up: 82,
                Qt.Key_Delete: 76,
                Qt.Key_Home: 74,
                Qt.Key_End: 77,
                Qt.Key_PageUp: 75,
                Qt.Key_PageDown: 78,
            }.get(key)
    if usage is None:
        raise ValueError("This key is not supported yet. Try a letter, arrow, or function key.")
    mask = 0
    if mods & Qt.ShiftModifier:
        mask |= 2
    if mods & Qt.AltModifier:
        mask |= 4
    # Qt maps ControlModifier to Command on macOS, MetaModifier to physical Control.
    if mods & Qt.ControlModifier:
        mask |= 8 if sys.platform == "darwin" else 1
    if mods & Qt.MetaModifier:
        mask |= 1 if sys.platform == "darwin" else 8
    return bytes([32, mask, int(usage), 0]).hex()
