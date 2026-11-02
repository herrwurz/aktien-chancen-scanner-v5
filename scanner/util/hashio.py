"""Canonical JSON, SHA-256, and exclusive cache writes without product imports."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exclusive(path: Path | str, raw: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("unsafe cache path")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("immutable cache conflict") from None
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
