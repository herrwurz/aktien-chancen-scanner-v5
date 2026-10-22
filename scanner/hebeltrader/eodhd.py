"""Optional, fixed-host EODHD collector. Never enabled by imports or a scheduler."""

import hashlib
import json
import logging
import os
import re
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from .market_snapshot import _credentials

BASE = "https://eodhd.com/api"
LICENSE = "https://eodhd.com/terms-conditions"
ENDPOINTS = {"eod", "splits", "div", "fundamentals", "exchange-details", "exchange-symbol-list"}


class _RedactApiToken(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if "api_token=" in message:
            record.msg = re.sub(r"(api_token=)[^&\s'\"]+", r"\1<redacted>", message)
            record.args = ()
        return True


def _safe_path(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("cache path escapes root")
    return path


def canonical(value):
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def exclusive(path, raw):
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


def read_record(root, manifest_sha256):
    root = Path(root).resolve()
    if not isinstance(manifest_sha256, str) or not re.fullmatch("[0-9a-f]{64}", manifest_sha256):
        raise ValueError("invalid manifest hash")
    manifest_file = root / "manifests" / (manifest_sha256 + ".json")
    if manifest_file.is_symlink() or not manifest_file.resolve().is_relative_to(root):
        raise ValueError("unsafe manifest")
    raw = manifest_file.read_bytes()
    if sha(raw) != manifest_sha256:
        raise ValueError("manifest integrity error")
    record = json.loads(raw)
    _credentials(record)
    digest = record["raw_sha256"]
    if not re.fullmatch("[0-9a-f]{64}", digest) or record["raw_file"] != "raw/" + digest + ".json":
        raise ValueError("invalid raw reference")
    path = root / record["raw_file"]
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("unsafe raw cache")
    body = path.read_bytes()
    if sha(body) != digest:
        raise ValueError("raw integrity error")
    return dict(record, manifest_sha256=manifest_sha256, payload=json.loads(body))


class EodhdClient:
    def __init__(
        self,
        root,
        *,
        allow_network=False,
        authorize_usage=False,
        max_requests=0,
        max_api_units=None,
        monthly_cost_eur="0",
        client=None,
        now=None,
        sleeper=time.sleep,
    ):
        cost = Decimal(str(monthly_cost_eur))
        if (
            not cost.is_finite()
            or not 0 <= cost <= 100
            or type(max_requests) is not int
            or max_requests < 0
        ):
            raise ValueError("EUR100 budget ceiling or request limit invalid")
        for name in ("httpx", *logging.Logger.manager.loggerDict):
            if name == "httpx" or name.startswith("httpcore"):
                logger = logging.getLogger(name)
                if not any(isinstance(f, _RedactApiToken) for f in logger.filters):
                    logger.addFilter(_RedactApiToken())
        self.root = Path(root).resolve()
        self.allow_network, self.authorize_usage = allow_network, authorize_usage
        self.remaining = max_requests
        self.remaining_units = max_requests if max_api_units is None else max_api_units
        if type(self.remaining_units) is not int or self.remaining_units < 0:
            raise ValueError("invalid API unit limit")
        self.api_units_spent = 0
        self.client, self.now, self.sleep = client, now or (lambda: datetime.now(UTC)), sleeper
        self.attempted_requests = 0

    def fetch(self, endpoint, symbol, *, start=None, end=None, delisted=False):
        if (
            endpoint not in ENDPOINTS
            or symbol in {".", ".."}
            or not isinstance(symbol, str)
            or not re.fullmatch(r"[A-Za-z0-9_^.-]{1,64}", symbol)
        ):
            raise ValueError("unsupported endpoint or symbol")
        for stamp in (start, end):
            if stamp is not None:
                date.fromisoformat(stamp)
        if start and end and start > end:
            raise ValueError("invalid date window")
        request = dict(
            endpoint=endpoint, symbol=symbol, start=start, end=end, delisted=bool(delisted)
        )
        key = sha(canonical(request))
        index = _safe_path(self.root, "requests/" + key + ".json")
        _safe_path(self.root, "raw")
        _safe_path(self.root, "manifests")
        if index.exists() or index.is_symlink():
            if index.is_symlink() or not index.resolve().is_relative_to(self.root):
                raise ValueError("unsafe cache index")
            record = read_record(self.root, json.loads(index.read_bytes())["manifest_sha256"])
            if record["request"] != request:
                raise ValueError("cache request mismatch")
            return record
        if not self.allow_network or not self.authorize_usage or self.remaining <= 0:
            raise ValueError(
                "cache miss; explicit network, provider-usage approval and request limit required"
            )
        token = os.environ.get("EODHD_API_TOKEN")
        if not token or not token.strip():
            raise ValueError("EODHD_API_TOKEN environment variable required")
        retrieved = self.now()
        if retrieved.utcoffset() is None:
            raise ValueError("aware retrieval clock required")
        params = dict(api_token=token, fmt="json")
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        if endpoint == "eod":
            params.update(period="d", order="a")
        if endpoint == "exchange-symbol-list":
            params["delisted"] = "1" if delisted else "0"
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=15, follow_redirects=False)
        try:
            response = None
            for attempt in range(3):
                weight = 10 if endpoint == "fundamentals" else 1
                if self.remaining <= 0 or self.remaining_units < weight:
                    break
                if self.attempted_requests:
                    self.sleep(min(2**attempt, 4))
                self.remaining -= 1
                self.remaining_units -= weight
                self.api_units_spent += weight
                self.attempted_requests += 1
                try:
                    response = client.get(
                        f"{BASE}/{endpoint}/{symbol}",
                        params=params,
                        timeout=15,
                        follow_redirects=False,
                    )
                except httpx.TransportError:
                    continue
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
            if response is None or response.status_code != 200:
                raise ValueError("EODHD request failed; bounded retries exhausted")
            raw = response.content
            if len(raw) > 32 * 1024 * 1024 or token.encode() in raw:
                raise ValueError("unsafe or oversized provider response")
            try:
                payload = json.loads(raw)
                _credentials(payload)
            except (ValueError, TypeError):
                raise ValueError("invalid provider JSON") from None
            if (
                not isinstance(payload, (dict, list))
                or isinstance(payload, dict)
                and ("error" in payload or "Error" in payload)
            ):
                raise ValueError("provider returned an error payload")
            digest = sha(raw)
            record = dict(
                request=request,
                raw_sha256=digest,
                raw_file="raw/" + digest + ".json",
                source_reference=f"{BASE}/{endpoint}/{symbol}",
                license=LICENSE,
                retrieved_at=retrieved.isoformat(),
                vendor="EODHD",
                volume_adjustment="split_adjusted_vendor" if endpoint == "eod" else None,
            )
            _credentials(record)
            manifest_sha = sha(canonical(record))
            exclusive(_safe_path(self.root, record["raw_file"]), raw)
            exclusive(
                _safe_path(self.root, "manifests/" + manifest_sha + ".json"), canonical(record)
            )
            exclusive(index, canonical(dict(manifest_sha256=manifest_sha)))
            return read_record(self.root, manifest_sha)
        finally:
            if own_client:
                client.close()
