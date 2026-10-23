"""Optional Tiingo EOD collector with immutable local replay."""

import json
import os
import re
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from .eodhd import canonical, exclusive, sha
from .market_snapshot import _credentials

BASE = "https://api.tiingo.com/tiingo/daily"
LICENSE = "https://www.tiingo.com/documentation/general/overview"


def _path(root, relative):
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate.is_symlink():
        raise ValueError("unsafe cache path")
    return candidate


def read_tiingo_record(root, manifest_sha256):
    root = Path(root).resolve()
    if not isinstance(manifest_sha256, str) or not re.fullmatch("[0-9a-f]{64}", manifest_sha256):
        raise ValueError("invalid manifest hash")
    raw = _path(root, f"manifests/{manifest_sha256}.json").read_bytes()
    if sha(raw) != manifest_sha256:
        raise ValueError("manifest integrity error")
    record = json.loads(raw)
    _credentials(record)
    digest = record["raw_sha256"]
    if record["raw_file"] != f"raw/{digest}.json":
        raise ValueError("invalid raw reference")
    body = _path(root, record["raw_file"]).read_bytes()
    if sha(body) != digest:
        raise ValueError("raw integrity error")
    payload = json.loads(body)
    _credentials(payload)
    return dict(record, manifest_sha256=manifest_sha256, payload=payload)


def import_tiingo_file(source, root, *, symbol, start, end, retrieved_at):
    """Archive an already downloaded Tiingo JSON file without opening a network client."""
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", symbol):
        raise ValueError("invalid Tiingo symbol")
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("invalid date window")
    retrieved_at = (
        datetime.fromisoformat(str(retrieved_at))
        if not isinstance(retrieved_at, datetime)
        else retrieved_at
    )
    if retrieved_at.utcoffset() is None:
        raise ValueError("aware retrieval clock required")
    raw = Path(source).read_bytes()
    payload = json.loads(raw)
    _credentials(payload)
    if not isinstance(payload, list):
        raise ValueError("invalid provider JSON")
    root = Path(root).resolve()
    request = dict(dataset="daily_prices", symbol=symbol, start=start, end=end)
    digest = sha(raw)
    record = dict(
        request=request,
        raw_sha256=digest,
        raw_file=f"raw/{digest}.json",
        source_reference=f"{BASE}/{symbol}/prices",
        license=LICENSE,
        retrieved_at=retrieved_at.isoformat(),
        vendor="Tiingo",
        data_scope="stock_eod_raw_and_adjusted; no German warrant quotes",
        import_mode="offline_existing_file",
    )
    manifest_sha = sha(canonical(record))
    index = _path(root, f"requests/{sha(canonical(request))}.json")
    if index.exists():
        existing = read_tiingo_record(root, json.loads(index.read_bytes())["manifest_sha256"])
        if existing["raw_sha256"] != digest:
            raise ValueError("immutable cache conflict")
        return existing
    exclusive(_path(root, record["raw_file"]), raw)
    exclusive(_path(root, f"manifests/{manifest_sha}.json"), canonical(record))
    exclusive(index, canonical({"manifest_sha256": manifest_sha}))
    return read_tiingo_record(root, manifest_sha)


class TiingoClient:
    def __init__(
        self,
        root,
        *,
        allow_network=False,
        authorize_usage=False,
        max_requests=0,
        monthly_cost_eur="0",
        client=None,
        now=None,
        sleeper=time.sleep,
        timeout=15,
    ):
        cost = Decimal(str(monthly_cost_eur))
        if (
            not cost.is_finite()
            or not 0 <= cost <= 100
            or type(max_requests) is not int
            or max_requests < 0
        ):
            raise ValueError("EUR100 budget ceiling or request limit invalid")
        self.root = Path(root).resolve()
        self.allow_network = allow_network
        self.authorize_usage = authorize_usage
        self.remaining = max_requests
        self.client = client
        self.now = now or (lambda: datetime.now(UTC))
        self.sleep = sleeper
        self.timeout = timeout
        self.attempted_requests = 0

    def fetch(self, symbol, *, start, end):
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", symbol):
            raise ValueError("invalid Tiingo symbol")
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        if start_date > end_date:
            raise ValueError("invalid date window")
        request = dict(dataset="daily_prices", symbol=symbol, start=start, end=end)
        request_key = sha(canonical(request))
        index = _path(self.root, f"requests/{request_key}.json")
        if index.exists():
            record = read_tiingo_record(
                self.root, json.loads(index.read_bytes())["manifest_sha256"]
            )
            if record["request"] != request:
                raise ValueError("cache request mismatch")
            return record
        if not self.allow_network or not self.authorize_usage or self.remaining <= 0:
            raise ValueError(
                "cache miss; explicit network, provider-usage approval and request limit required"
            )
        token = os.environ.get("TIINGO_API_TOKEN")
        if not token or not token.strip():
            raise ValueError("TIINGO_API_TOKEN environment variable required")
        retrieved = self.now()
        if retrieved.utcoffset() is None:
            raise ValueError("aware retrieval clock required")
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=False)
        response = None
        try:
            for attempt in range(3):
                if self.remaining <= 0:
                    break
                self.remaining -= 1
                self.attempted_requests += 1
                try:
                    response = client.get(
                        f"{BASE}/{symbol}/prices",
                        params={"startDate": start, "endDate": end},
                        headers={"Authorization": f"Token {token}"},
                        timeout=self.timeout,
                        follow_redirects=False,
                    )
                except httpx.TransportError:
                    response = None
                if response is not None and response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if attempt < 2:
                    self.sleep(min(2**attempt, 4))
            if response is None or response.status_code != 200:
                raise ValueError("Tiingo request failed; bounded retries exhausted")
            raw = response.content
            if len(raw) > 32 * 1024 * 1024 or token.encode() in raw:
                raise ValueError("unsafe or oversized provider response")
            payload = json.loads(raw)
            _credentials(payload)
            if not isinstance(payload, list):
                raise ValueError("invalid provider JSON")
            digest = sha(raw)
            record = dict(
                request=request,
                raw_sha256=digest,
                raw_file=f"raw/{digest}.json",
                source_reference=f"{BASE}/{symbol}/prices",
                license=LICENSE,
                retrieved_at=retrieved.isoformat(),
                vendor="Tiingo",
                data_scope="stock_eod_raw_and_adjusted; no German warrant quotes",
            )
            manifest_sha = sha(canonical(record))
            exclusive(_path(self.root, record["raw_file"]), raw)
            exclusive(_path(self.root, f"manifests/{manifest_sha}.json"), canonical(record))
            exclusive(index, canonical({"manifest_sha256": manifest_sha}))
            return read_tiingo_record(self.root, manifest_sha)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("invalid provider JSON") from None
        finally:
            if own_client:
                client.close()
