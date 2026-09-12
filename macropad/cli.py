# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

import argparse
import json
import math
import platform
import sys
import time
from pathlib import Path
from . import backend, descriptor, protocol, storage, learn


def number(value):
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use decimal or 0x-prefixed hexadecimal") from exc


def inspect(audit):
    rows = backend.enumerate_devices()
    if not rows:
        raise ValueError("G-LRA 36ae:2475 not found. Check USB cable and run list --all.")
    try:
        registry = backend.registry_descriptors()
    except Exception as exc:
        registry = {}
        audit.record("registry_error", message=str(exc))
    interfaces = []
    for path in dict.fromkeys(d["path"] for d in rows):
        infos = [d for d in rows if d["path"] == path]
        item = {"device": infos[0], "collections": infos}
        raw = registry.get(path)
        if raw is not None:
            item["descriptor_source"] = "macOS IORegistry (no device open)"
        else:
            try:
                with backend.open_device(infos[0]) as h:
                    raw = bytes(h.get_report_descriptor())
                item["descriptor_source"] = "hidapi"
            except OSError as exc:
                item["error"] = str(exc)
        if raw is not None:
            item["descriptor_hex"] = raw.hex()
            item["descriptor"] = descriptor.parse(raw)
        interfaces.append(item)
    return {
        "schema": "glra-macropad-diagnostics-v1",
        "created": storage.now(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "interfaces": interfaces,
        "configuration_written": False,
        "restorable": False,
    }


def parser():
    p = argparse.ArgumentParser(
        description="G-LRA k16_n3 diagnostics. This CLI does not change assignments."
    )
    p.add_argument("--log-dir", default="dumps/logs", help="Private JSONL audit directory")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("list", help="Enumerate devices without opening them")
    s.add_argument("--all", action="store_true", help="Also list other HID devices")
    for name in ("inspect", "dump"):
        s = sub.add_parser(name, help="Read descriptors; dump saves a checksummed file")
        s.add_argument("--out", required=name == "dump")
    for name in ("status", "backup", "watch", "feature"):
        s = sub.add_parser(name)
        s.add_argument("--path", help="Exact path from list; default: unique vendor interface")
        if name == "backup":
            s.add_argument("--out", required=True)
        if name == "watch":
            s.add_argument("--seconds", type=float, default=10)
        if name == "feature":
            s.add_argument("--report-id", type=number, required=True)
    s = sub.add_parser(
        "learn-key", help="Passively capture one macropad key; never changes settings"
    )
    s.add_argument("--seconds", type=float, default=120)
    s.add_argument("--out", required=True)
    s.add_argument("--backup", help="Optional existing dump to find candidate raw positions")
    s = sub.add_parser("decode", help="Decode assignments from an existing backup; no HID access")
    s.add_argument("file")
    s.add_argument("--profile", type=number, default=0)
    s = sub.add_parser("plan-key", help="Offline candidate packet only; cannot apply it")
    s.add_argument("file")
    s.add_argument("--profile", type=number, default=0)
    s.add_argument("--slot", type=number, required=True)
    s.add_argument("--usage", type=number, required=True)
    s.add_argument("--modifiers", type=number, default=0)
    s = sub.add_parser("report", help="Inspect captured Input/Output/Feature bytes offline")
    s.add_argument("--kind", choices=["input", "output", "feature"], required=True)
    s.add_argument("--hex", required=True)
    s.add_argument("--hidapi-prefix", action="store_true", help="First byte is HIDAPI report ID")
    s = sub.add_parser("verify", help="Verify dump checksum; no device access")
    s.add_argument("file")
    return p


def run(a, audit):
    if a.command == "learn-key":
        if not math.isfinite(a.seconds) or not 0 < a.seconds <= 300:
            raise ValueError("--seconds must be in (0, 300]")
        return learn.capture(a.seconds, a.out, audit, a.backup)
    if a.command == "list":
        return backend.enumerate_devices(a.all)
    if a.command in ("inspect", "dump"):
        result = inspect(audit)
        if a.out:
            storage.save(a.out, result)
        return result
    if a.command == "verify":
        data = storage.load(a.file)
        return {
            "checksum_valid": True,
            "schema": data.get("schema"),
            "restorable": data.get("restorable", False),
        }
    if a.command in ("decode", "plan-key"):
        data = storage.load(a.file)
        if a.command == "decode":
            return protocol.decode_assignments(data["assignments"][str(a.profile)])
        return protocol.write_plan(data, a.profile, a.slot, a.usage, a.modifiers)
    if a.command == "report":
        data = bytes.fromhex(a.hex)
        if not data or len(data) > 8192:
            raise ValueError("Expected 1..8192 bytes")
        return {
            "kind": a.kind,
            "byte_count": len(data),
            "hex": data.hex(),
            "report_id": data[0] if a.hidapi_prefix else None,
            "payload_hex": (data[1:] if a.hidapi_prefix else data).hex(),
            "sent": False,
        }
    if a.command == "watch" and (not math.isfinite(a.seconds) or not 0 < a.seconds <= 300):
        raise ValueError("--seconds must be in (0, 300]")
    info = backend.select(a.path, vendor_only=not bool(a.path))
    if a.command in ("status", "backup") and (info["usage_page"], info["usage"]) != (0xFF00, 2):
        raise ValueError("Protocol reads require the vendor interface")
    audit.record("open", device=info, exclusive=False)
    with backend.open_device(info) as device:
        parsed = descriptor.parse(bytes(device.get_report_descriptor()))
        if a.command in ("status", "backup"):
            reader = protocol.Reader(device, audit)
            if a.command == "status":
                return reader.status()
            # Avoid doing lengthy I/O if the requested backup already exists.
            if Path(a.out).exists():
                raise FileExistsError(a.out)
            result = {
                "schema": "glra-macropad-backup-v1",
                "created": storage.now(),
                "device": info,
                "descriptor_hex": protocol.VENDOR_DESCRIPTOR.hex(),
                "configuration_written": False,
                **reader.backup(),
            }
            storage.save(a.out, result)
            return {
                "saved": str(Path(a.out).resolve()),
                "restorable": False,
                "profiles": len(result["assignments"]),
                "assignment_double_read_equal": True,
                "extra_errors": {k: v["error"] for k, v in result["extra"].items() if "error" in v},
            }
        if a.command == "feature":
            report = next(
                (r for r in parsed["reports"] if r["type"] == "feature" and r["id"] == a.report_id),
                None,
            )
            if report is None:
                raise ValueError(
                    "Feature report is not declared by this descriptor; request refused"
                )
            length = report["hidapi_control_buffer_bytes"]
            if not 1 <= length <= 8192:
                raise ValueError("Unsafe report size")
            audit.record("get_feature_request", report_id=a.report_id, length=length)
            raw = bytes(device.get_feature_report(a.report_id, length))
            audit.record("feature", hex=raw.hex())
            return {"report_id": a.report_id, "hex": raw.hex()}
        if a.command == "watch":
            sizes = [r["interrupt_bytes"] for r in parsed["reports"] if r["type"] == "input"]
            if not sizes or max(sizes) > 8192:
                raise ValueError("No safe input report length available")
            end, count = time.monotonic() + a.seconds, 0
            while time.monotonic() < end:
                raw = bytes(device.read(max(sizes), 100))
                if raw:
                    audit.record("input_passive", hex=raw.hex())
                    print(json.dumps({"input_hex": raw.hex()}), flush=True)
                    count += 1
            return {"reports": count, "seconds": a.seconds, "output_reports_sent": 0}
    raise ValueError("Unknown command")


def main(argv=None):
    a = parser().parse_args(argv)
    audit = None
    try:
        audit = storage.Audit(a.log_dir)
        audit.record("start", command=a.command)
        result = run(a, audit)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        audit.record("complete")
        return 0
    except KeyboardInterrupt:
        if audit:
            audit.record("interrupted")
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, ImportError, AttributeError) as exc:
        if audit:
            audit.record("error", message=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        if isinstance(exc, OSError) and "open failed" in str(exc):
            print(
                "Close the web configurator. macOS may require Input Monitoring permission for the launching terminal/app.",
                file=sys.stderr,
            )
        return 1
    finally:
        if audit:
            audit.close()


if __name__ == "__main__":
    raise SystemExit(main())
