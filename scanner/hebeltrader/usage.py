"""Local append-only SHA chain; a usage audit, not a provider invoice or spending approval."""

import fcntl
import json
import os
from pathlib import Path

from .eodhd import canonical, sha
from .market_snapshot import _credentials


def _verify(raw):
    previous = None
    for line in raw.splitlines():
        record = json.loads(line)
        digest = record.pop("sha256")
        if record["previous_sha256"] != previous or sha(canonical(record)) != digest:
            raise ValueError("usage journal integrity error")
        _credentials(record)
        previous = digest
    return previous


def verify_usage(path):
    return _verify(Path(path).read_bytes())


def append_usage(path, event):
    _credentials(event)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        previous = _verify(stream.read())
        record = dict(event=event, previous_sha256=previous)
        record["sha256"] = sha(canonical(record))
        stream.write(canonical(record))
        stream.flush()
        os.fsync(stream.fileno())
    return record["sha256"]
