"""Immutable offline warrant quotes and conservative bid/ask execution research."""

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from .backtest_provider import _at
from .eodhd import canonical, exclusive, sha
from .market_snapshot import _credentials


def _path(root, relative):
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate.is_symlink():
        raise ValueError("unsafe archive path")
    return candidate


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid quote") from None
    if not result.is_finite() or result < 0:
        raise ValueError("invalid quote")
    return result


def import_quote_file(source, output_root, *, metadata):
    """Archive an authorized JSON export. Never downloads or rewrites provider data."""
    source, root = Path(source), Path(output_root).resolve()
    raw = source.read_bytes()
    source_format = "csv" if source.suffix.lower() == ".csv" else "json"
    if source_format == "csv":
        try:
            payload = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        except UnicodeDecodeError:
            raise ValueError("invalid quote CSV") from None
    else:
        payload = json.loads(raw)
    _credentials(metadata)
    required = {
        "wkn",
        "isin",
        "venue",
        "timezone",
        "currency",
        "source_reference",
        "license",
        "retrieved_at",
        "coverage_start",
        "coverage_end",
        "quote_kind",
    }
    optional = {
        "completeness_status",
        "trading_hours_reference",
        "quote_gap_review",
        "usage_rights_status",
        "reviewer",
        "reviewed_at",
    }
    if (
        not required.issubset(metadata)
        or set(metadata) - required - optional
        or any(not isinstance(metadata[k], str) or not metadata[k].strip() for k in required)
    ):
        raise ValueError("incomplete quote provenance")
    if metadata["quote_kind"] != "executable_bid_ask" or not re.fullmatch(
        r"[A-Z0-9]{4}", metadata["venue"]
    ):
        raise ValueError("unsupported quote provenance")
    zone = ZoneInfo(metadata["timezone"])
    start, end, retrieved = map(
        _at, (metadata["coverage_start"], metadata["coverage_end"], metadata["retrieved_at"])
    )
    if start >= end or retrieved < end:
        raise ValueError("invalid quote coverage")
    quotes, previous = [], None
    if not isinstance(payload, list):
        raise ValueError("quote JSON must be an array")
    for index, row in enumerate(payload):
        stamp = _at(row["timestamp"])
        if stamp.utcoffset() != stamp.astimezone(zone).utcoffset() or not start <= stamp <= end:
            raise ValueError("quote timestamp outside venue coverage")
        if previous is not None and stamp <= previous:
            raise ValueError("quotes must be strictly ordered")
        if row.get("quote_status", "executable") != "executable":
            raise ValueError("non-executable quote in executable archive")
        bid, ask = _decimal(row["bid"]), _decimal(row["ask"])
        if ask < bid:
            raise ValueError("crossed quote")
        if set(row) - {
            "timestamp",
            "bid",
            "ask",
            "bid_size",
            "ask_size",
            "quote_status",
            "last_tradable",
        }:
            raise ValueError("unexpected quote field")
        normalized = dict(
            timestamp=stamp.isoformat(),
            bid=str(bid),
            ask=str(ask),
            last_tradable=str(row.get("last_tradable", "")).lower() in {"1", "true", "yes"},
            quote_status="executable",
            payload_pointer=f"/{index}",
        )
        for size in ("bid_size", "ask_size"):
            if row.get(size) not in (None, ""):
                normalized[size] = str(_decimal(row[size]))
        quotes.append(normalized)
        previous = stamp
    digest = sha(raw)
    identity_key = sha(
        canonical(
            {k: metadata[k] for k in ("wkn", "isin", "venue", "coverage_start", "coverage_end")}
        )
    )
    index_path = _path(root, f"imports/{identity_key}.json")
    if index_path.exists():
        existing = json.loads(index_path.read_bytes())
        loaded = read_quote_archive(root, existing["manifest_sha256"])
        if loaded["raw_sha256"] != digest:
            raise ValueError("immutable quote archive conflict")
        return {
            k: loaded[k]
            for k in (
                "manifest_sha256",
                "format_version",
                "source_format",
                "raw_sha256",
                "raw_file",
                "quote_count",
                "metadata",
            )
        }
    raw_file = f"raw/{digest}.{source_format}"
    manifest = dict(
        format_version=2,
        source_format=source_format,
        metadata=metadata,
        raw_sha256=digest,
        raw_file=raw_file,
        quote_count=len(quotes),
    )
    manifest_sha = sha(canonical(manifest))
    exclusive(_path(root, raw_file), raw)
    exclusive(_path(root, f"manifests/{manifest_sha}.json"), canonical(manifest))
    exclusive(index_path, canonical({"manifest_sha256": manifest_sha}))
    return dict(manifest_sha256=manifest_sha, **manifest)


def read_quote_archive(root, manifest_sha256):
    root = Path(root).resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", str(manifest_sha256)):
        raise ValueError("invalid manifest hash")
    raw_manifest = _path(root, f"manifests/{manifest_sha256}.json").read_bytes()
    if sha(raw_manifest) != manifest_sha256:
        raise ValueError("manifest integrity error")
    manifest = json.loads(raw_manifest)
    raw = _path(root, manifest["raw_file"]).read_bytes()
    if sha(raw) != manifest["raw_sha256"]:
        raise ValueError("raw quote integrity error")
    if manifest.get("source_format", "json") == "csv":
        payload = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    else:
        payload = json.loads(raw)
    quotes = []
    for row in payload:
        normalized = dict(
            row,
            timestamp=_at(row["timestamp"]),
            bid=_decimal(row["bid"]),
            ask=_decimal(row["ask"]),
            quote_status=row.get("quote_status", "executable"),
            last_tradable=str(row.get("last_tradable", "")).lower() in {"1", "true", "yes"},
        )
        for size in ("bid_size", "ask_size"):
            if row.get(size) not in (None, ""):
                normalized[size] = _decimal(row[size])
        quotes.append(normalized)
    return dict(manifest, manifest_sha256=manifest_sha256, quotes=quotes)


@dataclass(frozen=True)
class DerivativeRules:
    target1: Decimal
    target2: Decimal
    stop1: Decimal
    partial_fraction: Decimal = Decimal("0.5")
    after_target1: str = "entry"
    loss_after_days: int | None = None
    loss_unit: str | None = None


def simulate_derivative_quotes(
    quotes,
    *,
    publication_at,
    last_trading_at,
    rules,
    capital=None,
    unit_size=1,
    fee_per_order=Decimal("0"),
    enforce_quote_size=False,
):
    result = dict(
        status="blocked",
        entry=None,
        events=[],
        return_pct=None,
        training_eligible=False,
        instrument="derivative",
        execution_model="entry at observed ask; exits at observed bid; fees unknown",
    )
    if (
        not isinstance(rules, DerivativeRules)
        or rules.after_target1 != "entry"
        or rules.partial_fraction != Decimal("0.5")
    ):
        return dict(result, blocker="invalid_or_unreviewed_rules")
    if rules.loss_after_days is not None and (
        rules.loss_after_days < 1 or rules.loss_unit not in {"calendar_days", "trading_sessions"}
    ):
        return dict(result, blocker="ambiguous_loss_time_unit")
    try:
        publication_at, last_trading_at = _at(publication_at), _at(last_trading_at)
        ordered = sorted(
            (
                dict(
                    q, timestamp=_at(q["timestamp"]), bid=_decimal(q["bid"]), ask=_decimal(q["ask"])
                )
                for q in quotes
            ),
            key=lambda q: q["timestamp"],
        )
    except (KeyError, TypeError, ValueError):
        return dict(result, blocker="invalid_quote_archive")
    ordered = [q for q in ordered if publication_at < q["timestamp"] <= last_trading_at]
    if not ordered:
        return dict(result, blocker="historical_bid_ask_unavailable")
    entry_quote, entry = ordered[0], ordered[0]["ask"]
    result["entry"] = {
        "timestamp": entry_quote["timestamp"].isoformat(),
        "price": str(entry),
        "side": "ask",
    }
    units = None
    if capital is not None:
        capital, fee_per_order = _decimal(capital), _decimal(fee_per_order)
        if type(unit_size) is not int or unit_size < 1 or capital <= fee_per_order:
            return dict(result, blocker="invalid_execution_cost_assumptions")
        affordable_lots = ((capital - fee_per_order) / entry / unit_size).to_integral_value(
            rounding=ROUND_FLOOR
        )
        units = int(affordable_lots) * unit_size
        if units < unit_size:
            return dict(result, blocker="insufficient_capital_for_minimum_unit")
        if enforce_quote_size and (
            entry_quote.get("ask_size") is None
            or _decimal(entry_quote["ask_size"]) < Decimal(units)
        ):
            return dict(result, blocker="insufficient_entry_quote_size")
        result["position"] = {
            "capital": str(capital),
            "units": units,
            "unit_size": unit_size,
            "entry_fee": str(fee_per_order),
            "uninvested_cash": str(capital - fee_per_order - entry * units),
        }
    first = None
    session_dates = []
    for q in ordered[1:]:
        if q["timestamp"].date() not in session_dates:
            session_dates.append(q["timestamp"].date())
        bid = q["bid"]
        stop = entry if first is not None else rules.stop1
        name = price = fraction = None
        if bid <= stop:
            name, price, fraction = "stop", bid, Decimal("0.5") if first is not None else Decimal(1)
        elif first is None and bid >= rules.target1:
            name, price, fraction = "target1", bid, Decimal("0.5")
        elif first is not None and bid >= rules.target2:
            name, price, fraction = "target2", bid, Decimal("0.5")
        elif first is None and rules.loss_after_days is not None and bid < entry:
            elapsed = (
                (q["timestamp"].date() - entry_quote["timestamp"].date()).days
                if rules.loss_unit == "calendar_days"
                else len(session_dates)
            )
            if elapsed >= rules.loss_after_days:
                name, price, fraction = "conditional_loss_exit", bid, Decimal(1)
        if name:
            if enforce_quote_size and units is not None:
                required_units = Decimal(units) * fraction
                if q.get("bid_size") is None or _decimal(q["bid_size"]) < required_units:
                    return dict(
                        result,
                        blocker="insufficient_exit_quote_size",
                        blocked_event=name,
                        blocked_at=q["timestamp"].isoformat(),
                    )
            result["events"].append(
                {
                    "event": name,
                    "timestamp": q["timestamp"].isoformat(),
                    "price": str(price),
                    "side": "bid",
                    "fraction": str(fraction),
                    "spread": str(q["ask"] - q["bid"]),
                }
            )
            if name == "target1":
                first = price
                continue
            average = price if first is None else first * Decimal("0.5") + price * Decimal("0.5")
            result.update(status="closed", return_pct=str((average - entry) / entry * 100))
            if units is not None:
                first_units = units // 2 if first is not None else 0
                second_units = units - first_units
                proceeds = (
                    price * units if first is None else first * first_units + price * second_units
                )
                order_count = 2 if first is None else 3
                final_cash = result["position"]["uninvested_cash"]
                final_cash = Decimal(final_cash) + proceeds - fee_per_order * (order_count - 1)
                result["cash_result"] = {
                    "gross_proceeds": str(proceeds),
                    "fees": str(fee_per_order * order_count),
                    "final_cash": str(final_cash),
                    "net_profit": str(final_cash - capital),
                    "return_pct": str((final_cash - capital) / capital * 100),
                }
            return result
    blocker = (
        "expiry_settlement_or_exit_quote_not_evidenced"
        if any(q.get("last_tradable") for q in ordered)
        else "no_verified_exit_before_last_available_quote"
    )
    result.update(status="open_or_censored", blocker=blocker)
    return result


def audit_quote_coverage(quotes, *, expected_start, expected_end, max_gap, levels=None):
    """Describe observable quote coverage without claiming continuous executability."""
    expected_start, expected_end = _at(expected_start), _at(expected_end)
    invalid_gap = not isinstance(max_gap, timedelta) or max_gap <= timedelta(0)
    if expected_start >= expected_end or invalid_gap:
        raise ValueError("invalid coverage window")
    ordered = sorted(
        (
            {
                **row,
                "timestamp": _at(row["timestamp"]),
                "bid": _decimal(row["bid"]),
                "ask": _decimal(row["ask"]),
            }
            for row in quotes
        ),
        key=lambda row: row["timestamp"],
    )
    missing = []
    points = [expected_start, *(row["timestamp"] for row in ordered), expected_end]
    for left, right in zip(points, points[1:], strict=False):
        if right - left > max_gap:
            missing.append(
                {
                    "start": left.isoformat(),
                    "end": right.isoformat(),
                    "duration_seconds": int((right - left).total_seconds()),
                }
            )
    spreads = [row["ask"] - row["bid"] for row in ordered]
    observed = {}
    for name, value in sorted((levels or {}).items()):
        value = _decimal(value)
        observed[name] = any(
            row["bid"] >= value if name.startswith("target") else row["bid"] <= value
            for row in ordered
        )
    return {
        "quote_count": len(ordered),
        "earliest_quote": ordered[0]["timestamp"].isoformat() if ordered else None,
        "latest_quote": ordered[-1]["timestamp"].isoformat() if ordered else None,
        "expected_start": expected_start.isoformat(),
        "expected_end": expected_end.isoformat(),
        "complete": bool(ordered) and not missing,
        "missing_intervals": missing,
        "spread": {
            "minimum": str(min(spreads)) if spreads else None,
            "maximum": str(max(spreads)) if spreads else None,
            "mean": str(sum(spreads) / len(spreads)) if spreads else None,
        },
        "observed_levels": observed,
        "scope": "observed executable bid/ask quotes; no execution claim",
    }


def verify_product_terms(candidate):
    required = (
        "wkn",
        "isin",
        "issuer",
        "ratio",
        "strike",
        "maturity",
        "last_trading_at",
        "reference_exchange",
        "settlement_currency",
        "fx_rule",
        "exercise",
        "settlement",
        "source_sha256",
        "source_reference",
    )
    missing = [key for key in required if not candidate.get(key)]
    verified = (
        not missing
        and candidate.get("review_status") == "approved"
        and bool(candidate.get("reviewer"))
        and bool(candidate.get("reviewed_at"))
    )
    return dict(
        candidate=candidate, verified=verified, missing=missing, requires_manual_review=not verified
    )


def quote_archive_ready(metadata):
    expected = {
        "completeness_status": "approved",
        "usage_rights_status": "approved_for_internal_research",
    }
    missing = [key for key, value in expected.items() if metadata.get(key) != value]
    missing.extend(
        key
        for key in ("trading_hours_reference", "quote_gap_review", "reviewer", "reviewed_at")
        if not metadata.get(key)
    )
    return {
        "approved": not missing,
        "missing": missing,
        "requires_manual_review": bool(missing),
    }
