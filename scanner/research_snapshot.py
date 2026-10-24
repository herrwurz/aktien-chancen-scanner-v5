"""Canonical, provenance-bound normalized research snapshots."""

import hashlib
import json
import os
from pathlib import Path

from scanner.research import AssetIdentity, CompanyEvent, CompanyFact


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def write_snapshot(path, *, assets, events, facts, coverage, raw_sources, generated_at):
    target = Path(path).resolve()
    sources = []
    for raw_path in raw_sources:
        raw = Path(raw_path).resolve()
        sources.append(
            {"path": os.path.relpath(raw, target.parent), "sha256": _sha(raw.read_bytes())}
        )
    payload = {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "assets": [AssetIdentity.model_validate(row).model_dump(mode="json") for row in assets],
        "events": [CompanyEvent.model_validate(row).model_dump(mode="json") for row in events],
        "facts": [CompanyFact.model_validate(row).model_dump(mode="json") for row in facts],
        "coverage": coverage,
        "raw_sources": sources,
    }
    envelope = {"payload": payload, "payload_sha256": _sha(_canonical(payload))}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_canonical(envelope) + b"\n")
    return envelope


def load_snapshot(path):
    target = Path(path).resolve()
    envelope = json.loads(target.read_bytes())
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or envelope.get("payload_sha256") != _sha(_canonical(payload)):
        raise ValueError("snapshot integrity error")
    for source in payload.get("raw_sources", []):
        raw = (target.parent / source["path"]).resolve()
        if _sha(raw.read_bytes()) != source["sha256"]:
            raise ValueError("raw source integrity error")
    payload["assets"] = [AssetIdentity.model_validate(row) for row in payload.get("assets", [])]
    payload["events"] = [CompanyEvent.model_validate(row) for row in payload.get("events", [])]
    payload["facts"] = [CompanyFact.model_validate(row) for row in payload.get("facts", [])]
    return payload
