"""Non-exclusive HIDAPI access and macOS registry descriptor fallback."""

import ctypes
import platform
import plistlib
import subprocess
from contextlib import contextmanager

VID, PID = 0x36AE, 0x2475


def enumerate_devices(all_devices=False):
    import hid

    rows = hid.enumerate() if all_devices else hid.enumerate(VID, PID)
    return [{**d, "path": d["path"].decode("utf-8", "surrogateescape")} for d in rows]


def select(path=None, vendor_only=True):
    rows = enumerate_devices()
    if path:
        rows = [d for d in rows if d["path"] == path]
    if vendor_only:
        rows = [d for d in rows if d["usage_page"] == 0xFF00 and d["usage"] == 2]
    unique = {d["path"]: d for d in rows}
    if len(unique) != 1:
        raise ValueError(
            f"Expected one matching interface, found {len(unique)}. Use list and --path."
        )
    return next(iter(unique.values()))


@contextmanager
def open_device(info):
    import hid

    if (info["vendor_id"], info["product_id"]) != (VID, PID):
        raise ValueError("Only the verified 36ae:2475 target may be opened")
    if platform.system() == "Darwin":
        # cython-hidapi does not expose this setting in Python. Use its own
        # bundled HIDAPI instance, with explicit ABI signatures; fail closed.
        lib = ctypes.CDLL(hid.__file__)
        setter = lib.hid_darwin_set_open_exclusive
        setter.argtypes, setter.restype = [ctypes.c_int], None
        getter = lib.hid_darwin_get_open_exclusive
        getter.argtypes, getter.restype = [], ctypes.c_int
        setter(0)
        if getter() != 0:
            raise RuntimeError("Cannot guarantee non-exclusive open")
    device = hid.device()
    try:
        device.open_path(info["path"].encode("utf-8", "surrogateescape"))
        yield device
    finally:
        device.close()


def registry_descriptors():
    if platform.system() != "Darwin":
        return {}
    proc = subprocess.run(
        ["/usr/sbin/ioreg", "-a", "-r", "-c", "IOHIDDevice"],
        capture_output=True,
        check=True,
        timeout=15,
    )
    result = {}
    for d in plistlib.loads(proc.stdout):
        if (d.get("VendorID"), d.get("ProductID")) == (VID, PID):
            desc = d.get("ReportDescriptor")
            if isinstance(desc, bytes):
                result[f"DevSrvsID:{d['IORegistryEntryID']}"] = desc
    return result
