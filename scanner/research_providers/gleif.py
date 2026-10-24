"""Bounded GLEIF legal-entity adapter; identity evidence, never company news."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scanner.hebeltrader.eodhd import canonical, exclusive, sha
from scanner.research import AssetIdentity

BASE = "https://api.gleif.org/api/v1/lei-records"
TERMS = "https://www.gleif.org/en/meta/lei-data-terms-of-use"


class GleifClient:
    def __init__(
        self,
        root,
        *,
        allow_network=False,
        max_requests=0,
        client=None,
        now=None,
    ):
        if type(max_requests) is not int or max_requests < 0:
            raise ValueError("invalid GLEIF request controls")
        self.root = Path(root).resolve()
        self.allow_network = allow_network
        self.remaining = max_requests
        self.client = client
        self.now = now or (lambda: datetime.now(UTC))

    def fetch_lei(self, lei):
        if not re.fullmatch(r"[A-Z0-9]{20}", str(lei or "")):
            raise ValueError("invalid LEI")
        request = {"dataset": "lei-record", "lei": lei, "url": f"{BASE}/{lei}"}
        key = sha(canonical(request))
        index = self.root / "requests" / f"{key}.json"
        if index.exists():
            manifest = json.loads(index.read_bytes())
            raw = (self.root / manifest["raw_file"]).read_bytes()
            if sha(raw) != manifest["raw_sha256"]:
                raise ValueError("GLEIF cache integrity error")
            return dict(manifest, payload=json.loads(raw), cache_hit=True)
        if not self.allow_network or self.remaining <= 0:
            raise ValueError("GLEIF cache miss; explicit network and request limit required")
        self.remaining -= 1
        own_client = self.client is None
        client = self.client or httpx.Client(timeout=20, follow_redirects=False)
        try:
            response = client.get(request["url"], timeout=20, follow_redirects=False)
            if response.status_code != 200:
                raise ValueError("GLEIF request failed")
            raw = response.content
            payload = json.loads(raw)
            retrieved = self.now()
            record = {
                "request": request,
                "raw_sha256": sha(raw),
                "raw_file": f"raw/{sha(raw)}.json",
                "source_reference": request["url"],
                "terms": TERMS,
                "license": "CC0-1.0",
                "retrieved_at": retrieved.isoformat(),
                "vendor": "GLEIF",
            }
            exclusive(self.root / record["raw_file"], raw)
            exclusive(index, canonical(record))
            return dict(record, payload=payload, cache_hit=False)
        except json.JSONDecodeError:
            raise ValueError("invalid GLEIF JSON") from None
        finally:
            if own_client:
                client.close()


def normalize_legal_entity(record):
    data = record["payload"].get("data")
    if not isinstance(data, dict) or data.get("type") != "lei-records":
        raise ValueError("unexpected GLEIF schema")
    attributes = data.get("attributes", {})
    entity = attributes.get("entity", {})
    registration = attributes.get("registration", {})
    lei = attributes.get("lei")
    name = entity.get("legalName", {}).get("name")
    country = entity.get("legalAddress", {}).get("country") or entity.get("jurisdiction")
    if not re.fullmatch(r"[A-Z0-9]{20}", str(lei or "")) or not name:
        raise ValueError("incomplete GLEIF legal entity")
    initial = registration.get("initialRegistrationDate")
    return AssetIdentity(
        asset_type="stock",
        name=name,
        lei=lei,
        country=country,
        valid_from=datetime.fromisoformat(initial.replace("Z", "+00:00")).date()
        if initial
        else None,
        quality_status="candidate",
        source_id="gleif-lei-record",
        retrieved_at=datetime.fromisoformat(record["retrieved_at"]),
        # A current record and its initial LEI date do not prove historical name validity.
        source_available_at=None,
    )
