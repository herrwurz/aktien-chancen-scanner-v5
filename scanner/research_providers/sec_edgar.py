"""SEC EDGAR universe and filing-event adapter with immutable caching."""

import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scanner.hebeltrader.eodhd import canonical, exclusive, sha
from scanner.research import AssetIdentity, CompanyEvent, EvidenceRecord, ProviderStatus

BASE = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_POLICY = "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data"
LOGGER = logging.getLogger(__name__)


def _age_seconds(now, retrieved_at):
    retrieved = datetime.fromisoformat(retrieved_at)
    return max(0, int((now - retrieved).total_seconds()))


class SecEdgarClient:
    def __init__(
        self,
        root,
        *,
        user_agent=None,
        allow_network=False,
        max_requests=0,
        dry_run=False,
        client=None,
        now=None,
        sleeper=time.sleep,
        min_interval=0.11,
        request_timeout_seconds=10,
    ):
        if (
            type(max_requests) is not int
            or max_requests < 0
            or min_interval < 0.1
            or not 1 <= request_timeout_seconds <= 30
        ):
            raise ValueError("invalid SEC request controls")
        self.root = Path(root).resolve()
        self.user_agent = user_agent or os.getenv("SEC_USER_AGENT")
        self.allow_network = allow_network
        self.remaining = max_requests
        self.dry_run = dry_run
        self.client = client
        self.now = now or (lambda: datetime.now(UTC))
        self.sleep = sleeper
        self.min_interval = min_interval
        self.request_timeout_seconds = request_timeout_seconds
        self.last_request_at = None

    def fetch(self, dataset, identifier=None):
        if dataset == "universe":
            url = TICKERS_URL
        elif dataset == "submissions" and re.fullmatch(r"\d{1,10}", str(identifier or "")):
            url = f"{BASE}/submissions/CIK{int(identifier):010d}.json"
        elif dataset == "companyfacts" and re.fullmatch(r"\d{1,10}", str(identifier or "")):
            url = f"{BASE}/api/xbrl/companyfacts/CIK{int(identifier):010d}.json"
        else:
            raise ValueError("unsupported SEC dataset or identifier")
        request = {"dataset": dataset, "identifier": identifier, "url": url}
        key = sha(canonical(request))
        index = self.root / "requests" / f"{key}.json"
        if index.exists():
            manifest = json.loads(index.read_bytes())
            raw = (self.root / manifest["raw_file"]).read_bytes()
            if sha(raw) != manifest["raw_sha256"]:
                raise ValueError("SEC cache integrity error")
            return dict(manifest, payload=json.loads(raw), cache_hit=True)
        if self.dry_run:
            return {"request": request, "status": "dry_run", "network_requests": 0}
        if not self.allow_network or self.remaining <= 0:
            raise ValueError("SEC cache miss; explicit network and request limit required")
        if not self.user_agent or "@" not in self.user_agent:
            raise ValueError("SEC_USER_AGENT with contact email required")
        own_client = self.client is None
        client = self.client or httpx.Client(
            timeout=self.request_timeout_seconds, follow_redirects=False
        )
        try:
            response = None
            for attempt in range(3):
                if self.remaining <= 0:
                    break
                self.remaining -= 1
                self.sleep(self.min_interval if self.last_request_at else 0)
                self.last_request_at = self.now()
                try:
                    response = client.get(
                        url,
                        headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
                        timeout=self.request_timeout_seconds,
                        follow_redirects=False,
                    )
                except httpx.TransportError:
                    response = None
                if response is not None and response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if attempt < 2:
                    self.sleep(min(2**attempt, 4))
            if response is None or response.status_code != 200:
                raise ValueError("SEC request failed; bounded retries exhausted")
            raw = response.content
            if len(raw) > 64 * 1024 * 1024:
                raise ValueError("SEC response exceeds size limit")
            payload = json.loads(raw)
            retrieved = self.now()
            record = {
                "request": request,
                "raw_sha256": sha(raw),
                "raw_file": f"raw/{sha(raw)}.json",
                "source_reference": url,
                "usage_policy": SEC_POLICY,
                "retrieved_at": retrieved.isoformat(),
                "vendor": "SEC_EDGAR",
            }
            exclusive(self.root / record["raw_file"], raw)
            exclusive(index, canonical(record))
            return dict(record, payload=payload, cache_hit=False)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("invalid SEC JSON") from None
        finally:
            if own_client:
                client.close()


def normalize_universe(record):
    payload = record["payload"]
    fields = payload.get("fields")
    if fields != ["cik", "name", "ticker", "exchange"] or not isinstance(payload.get("data"), list):
        raise ValueError("unexpected SEC universe schema")
    retrieved = datetime.fromisoformat(record["retrieved_at"])
    assets = []
    for cik, name, ticker, exchange in payload["data"]:
        if not cik or not name or not ticker:
            continue
        fund_name = re.search(
            r"\b(?:fund|etf|portfolio|muniholdings|muniyield|closed[- ]end)\b",
            name,
            re.IGNORECASE,
        )
        assets.append(
            AssetIdentity(
                asset_type="stock",
                name=name,
                ticker=ticker,
                cik=str(cik),
                exchange=exchange or None,
                country="US",
                instrument_type="fund" if fund_name else "unknown",
                instrument_type_status="inferred" if fund_name else "unknown",
                instrument_type_evidence="sec_legal_name_pattern" if fund_name else None,
                quality_status="incomplete",
                source_id="sec-company-tickers-exchange",
                retrieved_at=retrieved,
            )
        )
    return assets


def _category(form, items):
    item_set = {value.strip() for value in str(items or "").split(",")}
    if form in {"10-Q", "10-K", "20-F", "6-K"}:
        return "regulatory_filing"
    if form == "8-K" and "2.02" in item_set:
        return "regulatory_filing"
    if form == "8-K" and "5.02" in item_set:
        return "management_change"
    if form in {"SC 13D", "SC 13D/A"}:
        return "acquisition_or_stake"
    if form.startswith(("S-", "424B")):
        return "capital_action"
    return "regulatory_filing"


def normalize_submission_events(record, identity):
    payload = record["payload"]
    recent = payload.get("filings", {}).get("recent", {})
    required = {"accessionNumber", "filingDate", "acceptanceDateTime", "form"}
    if not required.issubset(recent):
        raise ValueError("unexpected SEC submissions schema")
    lengths = {len(recent[key]) for key in required}
    if len(lengths) != 1:
        raise ValueError("misaligned SEC submissions arrays")
    retrieved = datetime.fromisoformat(record["retrieved_at"])
    events = []
    for index in range(next(iter(lengths))):
        accession = recent["accessionNumber"][index]
        accepted = datetime.fromisoformat(
            recent["acceptanceDateTime"][index].replace("Z", "+00:00")
        )
        form = recent["form"][index]
        items = recent.get("items", [""] * next(iter(lengths)))[index]
        archive = f"{int(identity.cik)}/{accession.replace('-', '')}/{accession}-index.html"
        url = f"https://www.sec.gov/Archives/edgar/data/{archive}"
        facts = {
            "form": form,
            "document_type": form,
            "items": items,
            "accession_number": accession,
        }
        evidence = EvidenceRecord(
            source_id=f"sec:{accession}",
            url=url,
            title=f"SEC filing {form}",
            published_at=accepted,
            retrieved_at=retrieved,
            effective_at=accepted,
            source_available_at=accepted,
            source_kind="regulatory",
            facts=facts,
            content_sha256=record["raw_sha256"],
        )
        events.append(
            CompanyEvent(
                event_id=f"sec:{accession}",
                asset=identity,
                category=_category(form, items),
                headline=f"{identity.name}: SEC filing {form}",
                published_at=accepted,
                retrieved_at=retrieved,
                effective_at=accepted,
                evidence=evidence,
                facts=facts,
            )
        )
    return events


class SecUniverseProvider:
    def __init__(self, client):
        self.client = client

    def load_universe(self):
        now = self.client.now()
        try:
            record = self.client.fetch("universe")
            if record.get("status") == "dry_run":
                return [], ProviderStatus(provider="SEC_EDGAR", status="dry_run", retrieved_at=now)
            assets = normalize_universe(record)
            return assets, ProviderStatus(
                provider="SEC_EDGAR",
                status="ok",
                retrieved_at=datetime.fromisoformat(record["retrieved_at"]),
                record_count=len(assets),
                cache_hit=record["cache_hit"],
                data_age_seconds=_age_seconds(now, record["retrieved_at"]),
            )
        except ValueError as exc:
            LOGGER.warning("SEC universe provider unavailable: %s", type(exc).__name__)
            return [], ProviderStatus(
                provider="SEC_EDGAR",
                status="unavailable",
                retrieved_at=now,
                error_code=str(exc),
            )


class SecEventProvider:
    def __init__(self, client):
        self.client = client

    def load_events(self, identity):
        now = self.client.now()
        try:
            if not identity.cik:
                raise ValueError("CIK required for SEC events")
            record = self.client.fetch("submissions", identity.cik)
            if record.get("status") == "dry_run":
                return [], ProviderStatus(provider="SEC_EDGAR", status="dry_run", retrieved_at=now)
            events = normalize_submission_events(record, identity)
            return events, ProviderStatus(
                provider="SEC_EDGAR",
                status="ok",
                retrieved_at=datetime.fromisoformat(record["retrieved_at"]),
                record_count=len(events),
                cache_hit=record["cache_hit"],
                data_age_seconds=_age_seconds(now, record["retrieved_at"]),
            )
        except ValueError as exc:
            LOGGER.warning("SEC event provider unavailable: %s", type(exc).__name__)
            return [], ProviderStatus(
                provider="SEC_EDGAR",
                status="unavailable",
                retrieved_at=now,
                error_code=str(exc),
            )
