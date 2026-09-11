import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from macropad import lighting
from test_transactions import FakeReader


class LightReader(FakeReader):
    def __init__(self, directory):
        super().__init__(directory)
        self.light = lighting.DEFAULT
        self.rgb = bytes(432)

    def query(self, command):
        assert command == 10
        return bytes([0xAA, 10, 11, 0, 0]) + self.light + bytes(48)

    def memory(self, command, size, profile=0):
        return self.rgb if command == 19 else super().memory(command, size, profile)

    def write(self, data):
        assert list(self.directory.glob("*-lighting-before.json"))
        assert data[:6] == bytes([0, 6, 11, 11, 0, 0]) and len(data) == 65
        self.writes.append(data)
        self.light = data[6:17]
        self.ack = bytes([0xAA, 11, 1, 0, 0]) + self.light + bytes(48)
        if self.corrupt:
            self.rgb = bytes([1]) + bytes(431)
        return len(data)


class LightingTests(unittest.TestCase):
    def test_off_and_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            r = LightReader(folder)
            original = r.light
            off = lighting.for_mode(original, 0)
            self.assertEqual(off, bytes([1]) + bytes(10))
            result = lighting.write(r, {}, off, original.hex(), folder)
            self.assertTrue(result["verified"])
            lighting.write(r, {}, original, off.hex(), folder)
            self.assertEqual(r.light, original)

    def test_switch_on_from_off_has_visible_brightness(self):
        value = lighting.for_mode(bytes([1]) + bytes(10), 1)
        self.assertEqual(value[2], 1)
        self.assertGreater(value[3], 0)

    def test_unknown_mode_is_blocked(self):
        with self.assertRaises(ValueError):
            lighting.for_mode(lighting.DEFAULT, 99)

    def test_backup_failure_blocks_write(self):
        with tempfile.TemporaryDirectory() as folder:
            r = LightReader(folder)
            with patch("macropad.lighting.storage.save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    lighting.write(r, {}, lighting.for_mode(r.light, 1), r.light.hex(), folder)
            self.assertEqual(r.writes, [])

    def test_stale_value_blocks_write(self):
        with tempfile.TemporaryDirectory() as folder:
            r = LightReader(folder)
            with self.assertRaises(ValueError):
                lighting.write(r, {}, lighting.for_mode(r.light, 1), "00", folder)
            self.assertEqual(r.writes, [])

    def test_bad_ack_or_rgb_change_retains_error_backup(self):
        for fault in ("bad_ack", "corrupt"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                r = LightReader(folder)
                setattr(r, fault, True)
                with self.assertRaises(RuntimeError):
                    lighting.write(r, {}, lighting.for_mode(r.light, 1), r.light.hex(), folder)
                self.assertEqual(len(list(Path(folder).glob("*-lighting-error.json"))), 1)

    def test_fixed_colors_match_hardware_verified_packets(self):
        for index, hue in enumerate((0, 85, 170)):
            value = lighting.for_selection(lighting.DEFAULT, 1, index)
            self.assertEqual(value[2], 1)
            self.assertEqual(value[6:11], bytes([1, 255, hue, 255, 255]))
            self.assertEqual(lighting.color_index(value), index)
        with self.assertRaises(ValueError):
            lighting.for_selection(lighting.DEFAULT, 1, 7)

    def test_color_choice_only_applies_in_steady(self):
        self.assertEqual(lighting.for_selection(lighting.DEFAULT, 4, 0), lighting.DEFAULT)

    def test_rgb_mixture_and_invalid_channels(self):
        value = lighting.for_rgb(lighting.DEFAULT, 1, [64, 128, 112])
        self.assertEqual(value[6:11], bytes([1, 255, 116, 127, 128]))
        self.assertEqual(len(lighting.rgb_value(value)), 3)
        for rgb in ([256, 0, 0], [-1, 0, 0], [1, 2], [1.5, 0, 0]):
            with self.assertRaises(ValueError):
                lighting.for_rgb(lighting.DEFAULT, 1, rgb)
