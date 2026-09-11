"""Private, append-only audit records and checksummed diagnostic dumps."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"sha256": hashlib.sha256(canonical(data)).hexdigest(), "data": data}
    # Exclusive creation: an existing backup can never be overwritten.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(envelope, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def load(path):
    envelope = json.loads(Path(path).read_text())
    data = envelope["data"]
    if hashlib.sha256(canonical(data)).hexdigest() != envelope["sha256"]:
        raise ValueError("Dump checksum mismatch")
    return data


class Audit:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".jsonl"
        )
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.file = os.fdopen(fd, "w", buffering=1)

    def record(self, event, **fields):
        self.file.write(json.dumps({"time": now(), "event": event, **fields}) + "\n")
        self.file.flush()

    def close(self):
        self.file.close()
