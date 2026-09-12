# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

import unittest
from macropad.learn import decode, matches, BOOT_DESCRIPTOR, EXTENDED_DESCRIPTOR
from macropad.descriptor import parse


class LearnTests(unittest.TestCase):
    def test_boot_key_and_release(self):
        e = decode(bytes([0, 0, 0x5F, 0, 0, 0, 0, 0]), 0)
        self.assertEqual(e["names"], ["Numpad 7"])
        self.assertEqual(e["candidate_assignment_hex"], "20005f00")
        self.assertIsNone(decode(bytes(8), 0))

    def test_rollover_and_wrong_size(self):
        self.assertIsNone(decode(bytes([0, 0, 1, 0, 0, 0, 0, 0]), 0))
        self.assertIsNone(decode(bytes(7), 0))

    def test_nkro(self):
        raw = bytearray(16)
        raw[0] = 1
        raw[1] = 8
        raw[2 + 95 // 8] |= 1 << (95 % 8)
        self.assertEqual(decode(bytes(raw), 1)["candidate_assignment_hex"], "20085f00")

    def test_consumer(self):
        self.assertEqual(decode(bytes([3, 0xE9, 0]), 1)["candidate_assignment_hex"], "30e90000")
        self.assertIsNone(decode(bytes([3, 0, 0]), 1))

    def test_ambiguous_raw_positions_preserved(self):
        e = {"candidate_assignment_hex": "20005f00"}
        self.assertEqual(
            matches(e, {"assignments": {"0": "20005f0020005f00"}}),
            [{"read_parameter": 0, "raw_slot": 0}, {"read_parameter": 0, "raw_slot": 1}],
        )

    def test_descriptors_parse(self):
        self.assertEqual(parse(BOOT_DESCRIPTOR)["reports"][0]["payload_bytes"], 8)
        self.assertEqual(parse(EXTENDED_DESCRIPTOR)["reports"][0]["payload_bytes"], 15)
