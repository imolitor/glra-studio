# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from macropad import descriptor, protocol, storage, backend


class Log:
    def record(self, *args, **kwargs):
        pass


class Fake:
    def __init__(self, response):
        self.response, self.sent, self.pending = response, [], False

    def get_report_descriptor(self):
        return protocol.VENDOR_DESCRIPTOR

    def read(self, size, timeout):
        if self.pending:
            self.pending = False
            return self.response
        return []

    def write(self, packet):
        self.sent.append(packet)
        self.pending = True
        return len(packet)


class SafetyTests(unittest.TestCase):
    def test_descriptor_unnumbered_and_numbered(self):
        reports = descriptor.parse(protocol.VENDOR_DESCRIPTOR)["reports"]
        self.assertEqual([r["type"] for r in reports], ["input", "output"])
        self.assertTrue(
            all(r["payload_bytes"] == 64 and r["interrupt_bytes"] == 64 for r in reports)
        )
        r = descriptor.parse(bytes.fromhex("8503750195038102750595018103"))["reports"][0]
        self.assertEqual((r["bits"], r["payload_bytes"], r["interrupt_bytes"]), (8, 1, 2))

    def test_descriptor_rejects_truncation_and_stack_underflow(self):
        for raw in ("76ff", "fe02", "b4", "c0", "8500"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                descriptor.parse(bytes.fromhex(raw))

    def test_global_push_pop(self):
        parsed = descriptor.parse(bytes.fromhex("750895018100a4751095029100b4b100"))
        lengths = {r["type"]: r["payload_bytes"] for r in parsed["reports"]}
        self.assertEqual(lengths, {"input": 1, "output": 4, "feature": 1})

    def test_write_reset_bootloader_opcodes_blocked(self):
        for command in (9, 11, 13, 15, 16, 18, 20, 22, 64, 85, 90, 251, 252):
            with self.subTest(command=command), self.assertRaises(PermissionError):
                protocol.read_packet(command)

    def test_packet_profile_offset_and_padding(self):
        packet = protocol.read_packet(8, 560, 56, 5)
        self.assertEqual(len(packet), 65)
        self.assertEqual(packet[:9], bytes([0, 6, 8, 58, 0x30, 2, 0, 5, 0]))
        self.assertEqual(packet[9:], bytes(56))
        for args in ((8, 0, 56, 6), (8, 1, 56, 0), (12, 4090, 56, 0), (5, 0, 1, 0)):
            with self.assertRaises(ValueError):
                protocol.read_packet(*args)

    def test_live_status_fixture(self):
        raw = bytes.fromhex("aa050e000001006d2464000001640106000100").ljust(64, b"\0")
        f = Fake(raw)
        status = protocol.Reader(f, Log()).status()
        self.assertEqual(status["profile_count"], 6)
        self.assertEqual(status["internal_pid"], 0x246D)
        self.assertEqual(f.sent, [bytes([0, 6, 5]) + bytes(62)])

    def test_wrong_response_is_not_accepted(self):
        f = Fake(bytes([0xAA, 0xFA]) + bytes(62))
        with self.assertRaises(TimeoutError):
            protocol.Reader(f, Log(), timeout=0.001).query(5)

    def test_short_response_not_accepted(self):
        with self.assertRaises(TimeoutError):
            protocol.Reader(Fake(bytes([0xAA, 5])), Log(), timeout=0.001).query(5)

    def test_changed_descriptor_blocks_output(self):
        f = Fake([])
        f.get_report_descriptor = lambda: b""
        with self.assertRaises(ValueError):
            protocol.Reader(f, Log())
        self.assertEqual(f.sent, [])

    def test_ambiguous_device_selection(self):
        rows = [{"path": x, "usage_page": 0xFF00, "usage": 2} for x in ("a", "b")]
        with patch.object(backend, "enumerate_devices", return_value=rows):
            with self.assertRaises(ValueError):
                backend.select()
            self.assertEqual(backend.select("a")["path"], "a")

    def test_backup_checksum_and_exclusive_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "dump.json"
            storage.save(file, {"a": 1})
            self.assertEqual(storage.load(file), {"a": 1})
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                storage.save(file, {"a": 2})
            envelope = json.loads(file.read_text())
            envelope["data"]["a"] = 3
            file.write_text(json.dumps(envelope))
            with self.assertRaises(ValueError):
                storage.load(file)

    def test_unstable_backup_fails(self):
        reader = protocol.Reader(Fake([]), Log())
        reader.status = lambda: {"profile_count": 1}
        values = iter([bytes(576), bytes([1]) + bytes(575)])
        reader.memory = lambda *args: next(values)
        with self.assertRaisesRegex(ValueError, "changed between reads"):
            reader.backup()

    def test_wrong_offset_not_accepted(self):
        response = bytes([0xAA, 7, 58, 56, 0]) + bytes(59)
        with self.assertRaises(TimeoutError):
            protocol.Reader(Fake(response), Log(), timeout=0.001).query(8, 0, 56)

    def test_offline_plan_is_disabled_and_preserves_before(self):
        dump = {"assignment_double_read_equal": True, "assignments": {"0": "20000400" * 144}}
        result = protocol.write_plan(dump, 0, 2, 104, 8)
        self.assertFalse(result["enabled"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["before"], "20000400")
        packet = bytes.fromhex(result["candidate_hidapi_output_hex"])
        self.assertEqual(packet[:13], bytes([0, 6, 16, 7, 8, 0, 0, 0, 0, 32, 8, 104, 0]))


if __name__ == "__main__":
    unittest.main()
