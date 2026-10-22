"""Immutable offline warrant quotes and conservative bid/ask execution research."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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
        bid, ask = _decimal(row["bid"]), _decimal(row["ask"])
        if ask < bid:
            raise ValueError("crossed quote")
        if set(row) - {"timestamp", "bid", "ask", "last_tradable"}:
            raise ValueError("unexpected quote field")
        quotes.append(
            dict(
                timestamp=stamp.isoformat(),
                bid=str(bid),
                ask=str(ask),
                last_tradable=bool(row.get("last_tradable")),
                payload_pointer=f"/{index}",
            )
        )
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
                "raw_sha256",
                "raw_file",
                "quote_count",
                "metadata",
            )
        }
    raw_file = f"raw/{digest}.json"
    manifest = dict(
        format_version=1,
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
    payload = json.loads(raw)
    quotes = []
    for row in payload:
        quotes.append(
            dict(
                row,
                timestamp=_at(row["timestamp"]),
                bid=_decimal(row["bid"]),
                ask=_decimal(row["ask"]),
            )
        )
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


def simulate_derivative_quotes(quotes, *, publication_at, last_trading_at, rules):
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
            return result
    result.update(status="open_or_censored", blocker="no_verified_exit_before_last_available_quote")
    return result


def verify_product_terms(candidate):
    required = (
        "wkn",
        "isin",
        "issuer",
        "ratio",
        "strike",
        "maturity",
        "last_trading_at",
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
