"""Bounded, teaser-independent US EOD pilot and reproducible audit output."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

from scanner.hebeltrader.tiingo import TiingoClient
from scanner.research import AssetIdentity

from .models import InstrumentListing
from .providers import normalize_tiingo

EXCHANGES = {
    "Nasdaq": ("XNAS", "NASDAQ"),
    "NASDAQ": ("XNAS", "NASDAQ"),
    "NYSE": ("XNYS", "NYSE"),
    "NYSE American": ("XASE", "NYSE American"),
}


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
        asset_id=f"cik:{identity.cik}",
        cik=str(identity.cik).zfill(10),
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
    monotonic=time.monotonic,
):
    if coverage_kind not in {"real_provider_archive", "synthetic_fixture"}:
        raise ValueError("invalid coverage kind")
    selected = select_us_pilot(index, as_of=as_of, count=count)
    if len(selected) < count:
        base = _base_report(selected, monthly_cost_eur, coverage_kind)
        return {**base, "status": "insufficient_sec_universe"}
    if max_requests < count:
        raise ValueError("request ceiling must cover selected pilot instruments")
    if client is None and allow_network and authorize_usage and not os.getenv("TIINGO_API_TOKEN"):
        rows = [_blocked_row(row, "blocked_missing_credentials") for row in selected]
        base = _base_report(selected, monthly_cost_eur, coverage_kind)
        return {
            **base,
            "status": "blocked_missing_credentials",
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
            batch = normalize_tiingo(record, listing)
            imported = market_archive.import_batch(batch)
            rows.append(
                _instrument_row(
                    identity,
                    status="imported",
                    session_count=len(batch.bars),
                    actions=len(batch.actions),
                    imported=imported,
                    raw_sha256=batch.raw_sha256,
                    manifest_sha256=batch.manifest_sha256,
                    retrieved_at=batch.retrieved_at.isoformat(),
                )
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            rows.append(_blocked_row(identity, _error_code(exc)))
    successful = sum(row["status"] in {"imported", "up_to_date"} for row in rows)
    real_measured = coverage_kind == "real_provider_archive" and successful > 0
    base = _base_report(selected, monthly_cost_eur, coverage_kind)
    return {
        **base,
        "status": "ok" if successful == len(selected) else "partial",
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


def _instrument_row(identity, *, status, session_count, actions, **extra):
    return {
        "asset_id": f"cik:{identity.cik}",
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


def _blocked_row(identity, code):
    return _instrument_row(identity, status=code, session_count=0, actions=0)


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
    return {"json": json_path, "csv": csv_path, "sha256": hashlib.sha256(raw).hexdigest()}
