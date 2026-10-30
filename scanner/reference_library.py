"""Read-only historical library for the web UI; never a ranking input."""

import hashlib
import os
import tempfile
from pathlib import Path

import httpx

from scanner.hebeltrader.detective.reference_cases import historical_summary, load_references

SOURCE = (
    "https://raw.githubusercontent.com/herrwurz/aktien-chancen-scanner-v5/"
    "f24836d6b06424f37e60e77688e502e4d7555c7d/data/hebeltrader/teaser-cases.json"
)
SHA256 = "13cb84b6ddb67ee5599a470b530101c015375749fd39da44f0b35e64b18c8817"


def download():
    data = bytearray()
    with httpx.stream("GET", SOURCE, timeout=30, follow_redirects=False) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 512_000:
                raise ValueError("Reference download too large")
    return bytes(data)


def _path(state):
    return Path(state) / "references" / (SHA256 + ".json")


def library(state):
    path = _path(state)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Reference integrity check failed")
    data = load_references(path)
    return {
        "cases": data["cases"],
        "summary": historical_summary(data),
        "source": SOURCE,
        "sha256": SHA256,
        "evaluation_class": "development_regression",
    }


def import_library(state):
    path = _path(state)
    if path.exists():
        return library(state)
    payload = download()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError("Reference download integrity check failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        load_references(temporary)
        temporary.chmod(0o444)
        try:
            os.link(temporary, path)  # Atomic publish, never overwrite an existing archive.
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return library(state)
