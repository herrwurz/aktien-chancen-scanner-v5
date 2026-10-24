"""Immutable SHA-256 cache shared by news providers."""

import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class ImmutableNewsCache:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, request):
        index = self.root / "requests" / f"{digest(canonical(request))}.json"
        if not index.exists():
            return None
        manifest = json.loads(index.read_text())
        raw = (self.root / manifest["raw_file"]).read_bytes()
        if digest(raw) != manifest["raw_sha256"]:
            raise ValueError("news cache integrity error")
        return raw, manifest

    def write(self, request, raw, metadata):
        raw_sha = digest(raw)
        raw_path = self.root / "raw" / f"{raw_sha}.json"
        index = self.root / "requests" / f"{digest(canonical(request))}.json"
        for path, payload in (
            (raw_path, raw),
            (
                index,
                canonical(
                    {
                        **metadata,
                        "raw_sha256": raw_sha,
                        "raw_file": str(raw_path.relative_to(self.root)),
                    }
                ),
            ),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != payload:
                raise ValueError("immutable news cache conflict")
            if not path.exists():
                path.write_bytes(payload)
        return {**metadata, "raw_sha256": raw_sha, "raw_file": str(raw_path.relative_to(self.root))}
