"""Bounded, teaser-independent US EOD pilot and reproducible audit output."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scanner.hebeltrader.tiingo import TiingoClient
from scanner.research import AssetIdentity
from scanner.research_index.builder import build_index
from scanner.research_index.identity import canonical_cik, stable_asset_id
from scanner.research_providers.sec_edgar import normalize_universe

from .models import ExchangeCalendar, InstrumentListing, MarketDataBatch
from .providers import normalize_tiingo

EXCHANGES = {
    "Nasdaq": ("XNAS", "NASDAQ"),
    "NASDAQ": ("XNAS", "NASDAQ"),
    "NYSE": ("XNYS", "NYSE"),
    "NYSE American": ("XASE", "NYSE American"),
}
SEC_UNIVERSE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def discover_sec_universe_request(root):
    root = Path(root).resolve()
    matches = []
    for path in sorted(root.glob("**/requests/*.json")):
        try:
            manifest = json.loads(path.read_bytes())
            request = manifest.get("request", {})
            is_universe = (
                request.get("dataset") == "universe"
                or manifest.get("source_reference") == SEC_UNIVERSE_URL
            )
            if manifest.get("vendor") != "SEC_EDGAR" or not is_universe:
                continue
            cache_root = path.parent.parent.resolve()
            relative = Path(manifest["raw_file"])
            raw_path = (cache_root / relative).resolve()
            if relative.is_absolute() or not raw_path.is_relative_to(cache_root):
                raise ValueError("unsafe SEC raw archive path")
            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != manifest["raw_sha256"]:
                raise ValueError("SEC universe cache integrity error")
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            continue
        matches.append(path.resolve())
    if not matches:
        raise ValueError("no integrity-checked SEC universe manifest found")
    if len(matches) != 1:
        raise ValueError("multiple SEC universe manifests found")
    return matches[0]


def validate_sec_index_audit(path, index, as_of):
    if as_of.utcoffset() is None:
        raise ValueError("aware as-of required")
    audit = json.loads(Path(path).read_bytes())
    retrieved_at = datetime.fromisoformat(audit["sec_retrieved_at"])
    if retrieved_at.utcoffset() is None:
        raise ValueError("SEC audit retrieval timestamp must be aware")
    if audit.get("index_payload_sha256") != index.manifest.payload_sha256:
        raise ValueError("SEC index audit mismatch")
    if as_of < retrieved_at:
        raise ValueError("as-of precedes SEC archive retrieval")
    return audit


def build_sec_pilot_index(sec_request_path, output_path):
    request_path = Path(sec_request_path).resolve()
    cache_root = request_path.parent.parent
    manifest = json.loads(request_path.read_bytes())
    relative = Path(manifest["raw_file"])
    raw_path = (cache_root / relative).resolve()
    if relative.is_absolute() or not raw_path.is_relative_to(cache_root):
        raise ValueError("unsafe SEC raw archive path")
    raw = raw_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.get("raw_sha256"):
        raise ValueError("SEC universe cache integrity error")
    record = {**manifest, "payload": json.loads(raw)}
    groups = {}
    for identity in normalize_universe(record):
        groups.setdefault(canonical_cik(identity.cik), []).append(identity)
    included, ambiguous, unsupported = [], [], []
    for cik, listings in sorted(groups.items()):
        distinct = {(row.ticker, row.exchange) for row in listings}
        if len(distinct) != 1:
            ambiguous.append({"cik": cik, "tickers": sorted({row.ticker for row in listings})})
            continue
        identity = listings[0].model_copy(update={"cik": cik})
        venue = EXCHANGES.get(identity.exchange)
        if venue is None:
            unsupported.append(
                {"cik": cik, "ticker": identity.ticker, "exchange": identity.exchange}
            )
            continue
        included.append(identity.model_copy(update={"mic": venue[0]}))
    index_manifest = build_index(output_path, assets=included, events=[], facts=[], news=[])
    return {
        "schema_version": "1.0",
        "sec_raw_sha256": digest,
        "sec_retrieved_at": manifest["retrieved_at"],
        "source_reference": manifest["source_reference"],
        "total_listings": sum(len(rows) for rows in groups.values()),
        "unique_issuers": len(groups),
        "included_issuers": len(included),
        "excluded_ambiguous_issuers": ambiguous,
        "excluded_unsupported_exchanges": unsupported,
        "index_payload_sha256": index_manifest.payload_sha256,
        "selection_performed": False,
    }


def load_calendar_csv(
    path,
    *,
    supported_mics,
    timezone,
    source_reference,
    retrieved_at,
):
    path = Path(path)
    raw = path.read_bytes()
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    if reader.fieldnames != ["session_date", "close_at"]:
        raise ValueError("calendar CSV requires session_date,close_at")
    sessions = {}
    for row in reader:
        day = date.fromisoformat(row["session_date"])
        if day in sessions:
            raise ValueError("duplicate calendar session")
        sessions[day] = datetime.fromisoformat(row["close_at"])
    return ExchangeCalendar(
        supported_mics={value.strip() for value in supported_mics.split(",") if value.strip()},
        timezone=timezone,
        source_reference=source_reference,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        retrieved_at=retrieved_at,
        sessions=sessions,
    )


def _rank(identity):
    return hashlib.sha256(f"market-pilot-v1:cik:{identity.cik}".encode()).hexdigest()


def select_us_pilot(index, *, as_of, count=10):
    if not 1 <= count <= 50:
        raise ValueError("pilot count must be between 1 and 50")
    eligible = [
        row
        for row in index.market_universe(as_of=as_of)
        if row.asset_type == "stock"
        and row.country == "US"
        and row.cik
        and row.ticker
        and row.instrument_type != "fund"
        and (row.valid_from is None or row.valid_from <= as_of.date())
        and (row.valid_to is None or row.valid_to >= as_of.date())
    ]
    by_cik = {}
    for row in eligible:
        by_cik.setdefault(row.cik, row)
    return sorted(by_cik.values(), key=_rank)[:count]


def _listing(identity: AssetIdentity):
    venue = EXCHANGES.get(identity.exchange)
    if venue is None:
        raise ValueError("unsupported or missing SEC exchange")
    mic, exchange = venue
    return InstrumentListing(
        asset_id=stable_asset_id(identity),
        cik=canonical_cik(identity.cik),
        ticker=identity.ticker,
        exchange=exchange,
        mic=mic,
        currency="USD",
        timezone="America/New_York",
        provider_symbol=identity.ticker,
    )


def _next_day(value):
    return (date.fromisoformat(value) + timedelta(days=1)).isoformat()


def run_tiingo_pilot(
    *,
    index,
    market_archive,
    raw_cache,
    start,
    end,
    as_of,
    allow_network=False,
    authorize_usage=False,
    max_requests=0,
    monthly_cost_eur="0",
    client=None,
    count=10,
    coverage_kind="real_provider_archive",
    max_duration_seconds=120,
    calendar: ExchangeCalendar | None = None,
    monotonic=time.monotonic,
):
    try:
        cost = Decimal(str(monthly_cost_eur))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("EUR20 project budget invalid") from None
    if not cost.is_finite() or not 0 <= cost <= 20:
        raise ValueError("EUR20 project budget exceeded")
    if not 1 <= max_duration_seconds <= 300:
        raise ValueError("invalid pilot duration ceiling")
    if coverage_kind not in {"real_provider_archive", "synthetic_fixture"}:
        raise ValueError("invalid coverage kind")
    selected = select_us_pilot(index, as_of=as_of, count=count)
    if len(selected) < count:
        base = _base_report(selected, monthly_cost_eur, coverage_kind)
        return {
            **base,
            "status": "blocked",
            "blocker_code": "insufficient_sec_universe",
            "instruments": [],
            "successful_instruments": 0,
            "successful_sources": [],
            "requests_attempted": 0,
        }
    if max_requests < count:
        raise ValueError("request ceiling must cover selected pilot instruments")
    if client is None and allow_network and authorize_usage and not os.getenv("TIINGO_API_TOKEN"):
        rows = [_blocked_row(row, "blocked_missing_credentials") for row in selected]
        base = _base_report(selected, monthly_cost_eur, coverage_kind)
        return {
            **base,
            "status": "blocked",
            "blocker_code": "blocked_missing_credentials",
            "instruments": rows,
            "successful_instruments": 0,
            "successful_sources": [],
            "requests_attempted": 0,
            "duration_seconds": 0.0,
            "archive_sha256": market_archive.logical_sha256(),
        }
    provider = client or TiingoClient(
        raw_cache,
        allow_network=allow_network,
        authorize_usage=authorize_usage,
        max_requests=max_requests,
        monthly_cost_eur=monthly_cost_eur,
    )
    started = monotonic()
    rows = []
    for identity in selected:
        if monotonic() - started >= max_duration_seconds:
            rows.extend(
                _blocked_row(remaining, "runtime_limit_reached")
                for remaining in selected[len(rows) :]
            )
            break
        before_requests = getattr(provider, "attempted_requests", 0)
        try:
            listing = _listing(identity)
            incremental_start = start
            latest = market_archive.latest_session(listing.asset_id, "Tiingo")
            if latest:
                incremental_start = max(start, _next_day(latest))
            if incremental_start > end:
                rows.append(
                    _instrument_row(identity, status="up_to_date", session_count=0, actions=0)
                )
                continue
            record = provider.fetch(identity.ticker, start=incremental_start, end=end)
            requests_used = getattr(provider, "attempted_requests", 0) - before_requests
            batch = normalize_tiingo(record, listing, calendar=calendar)
            imported = market_archive.import_batch(batch)
            audit = audit_batch(batch, calendar=calendar, start=start, end=end, as_of=as_of)
            rows.append(
                _instrument_row(
                    identity,
                    status=(
                        "imported"
                        if audit["calendar_status"] != "verified_missing_sessions"
                        else "incomplete"
                    ),
                    imported=imported,
                    raw_sha256=batch.raw_sha256,
                    manifest_sha256=batch.manifest_sha256,
                    retrieved_at=batch.retrieved_at.isoformat(),
                    api_requests=requests_used,
                    **audit,
                )
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            rows.append(
                _blocked_row(
                    identity,
                    _error_code(exc),
                    api_requests=getattr(provider, "attempted_requests", 0) - before_requests,
                )
            )
    successful = sum(row["status"] in {"imported", "up_to_date"} for row in rows)
    real_measured = coverage_kind == "real_provider_archive" and successful > 0
    base = _base_report(selected, monthly_cost_eur, coverage_kind)
    accepted = bool(
        coverage_kind == "real_provider_archive"
        and successful == len(selected)
        and all(row.get("minimum_250_sessions_met") for row in rows)
        and all(row.get("calendar_status") == "verified_complete" for row in rows)
    )
    status = "accepted" if accepted else "partial"
    blocker_code = None
    if coverage_kind == "synthetic_fixture":
        status = "blocked"
        blocker_code = "synthetic_fixture_not_real_acceptance"
    elif successful == 0:
        status = "blocked"
        blocker_code = "all_provider_requests_failed"
    return {
        **base,
        "status": status,
        "blocker_code": blocker_code,
        "instruments": rows,
        "successful_instruments": successful,
        "successful_sources": ["Tiingo"] if successful else [],
        "requests_attempted": getattr(provider, "attempted_requests", 0),
        "duration_seconds": round(monotonic() - started, 6),
        "real_provider_coverage_measured": real_measured,
        "archive_sha256": market_archive.logical_sha256(),
    }


def _base_report(selected, cost, coverage_kind):
    return {
        "schema_version": "1.0",
        "provider": "Tiingo",
        "selection_method": "stable_sha256_sec_cik_v1",
        "selection_independent_of_teaser": True,
        "selected_count": len(selected),
        "available_sources": ["Tiingo"],
        "cost_eur": str(cost),
        "coverage_kind": coverage_kind,
        "real_provider_coverage_measured": False,
        "training_eligible": False,
        "calendar_policy": "independent_calendar_required; weekdays_not_inferred",
    }


def _instrument_row(identity, *, status, session_count=0, actions=0, **extra):
    return {
        "asset_id": stable_asset_id(identity),
        "ticker": identity.ticker,
        "exchange": identity.exchange,
        "status": status,
        "session_count": session_count,
        "minimum_250_sessions_met": session_count >= 250 if status == "imported" else None,
        "corporate_action_count": actions,
        "calendar_status": "unavailable_not_inferred",
        "missing_sessions": None,
        "historical_availability_verified": False,
        **extra,
    }


def _blocked_row(identity, code, **extra):
    extra.setdefault("api_requests", 0)
    return _instrument_row(identity, status=code, session_count=0, actions=0, **extra)


def audit_batch(batch: MarketDataBatch, *, calendar, start, end, as_of):
    dates = {bar.session_date for bar in batch.bars}
    missing = None
    calendar_status = "unavailable_not_inferred"
    if calendar is not None:
        expected = {
            day
            for day in calendar.sessions
            if date.fromisoformat(start) <= day <= date.fromisoformat(end)
        }
        missing = sorted((expected - dates), key=lambda day: day.isoformat())
        missing = [day.isoformat() for day in missing]
        calendar_status = "verified_missing_sessions" if missing else "verified_complete"
    latest = max((bar.session_end_at for bar in batch.bars), default=None)
    return {
        "session_count": len(batch.bars),
        "minimum_250_sessions_met": len(batch.bars) >= 250,
        "corporate_action_count": len(batch.actions),
        "split_count": sum(action.kind == "split" for action in batch.actions),
        "dividend_count": sum(action.kind == "dividend" for action in batch.actions),
        "other_action_count": sum(action.kind == "other" for action in batch.actions),
        "calendar_status": calendar_status,
        "calendar_sha256": calendar.raw_sha256 if calendar else None,
        "missing_sessions": missing,
        "data_age_seconds": max(0, int((as_of - latest).total_seconds())) if latest else None,
    }


def _error_code(error):
    text = str(error)
    if "environment variable required" in text:
        return "blocked_missing_credentials"
    if "unsupported or missing SEC exchange" in text:
        return "blocked_unsupported_exchange"
    if "bounded retries exhausted" in text:
        return "provider_retries_exhausted"
    if "explicit network" in text:
        return "cache_miss_network_disabled"
    return "provider_data_error"


def write_pilot_report(report, output_prefix):
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix.with_suffix(".json")
    csv_path = prefix.with_suffix(".csv")
    sha_path = prefix.with_suffix(".sha256")
    raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    json_path.write_bytes(raw)
    rows = report.get("instruments", [])
    fields = sorted({key for row in rows for key in row}) or ["asset_id", "status"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )
    digest = hashlib.sha256(raw).hexdigest()
    sha_path.write_text(f"{digest}  {json_path.name}\n")
    return {
        "json": json_path,
        "csv": csv_path,
        "sha256_file": sha_path,
        "sha256": digest,
    }
