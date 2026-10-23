"""Pilot-only evidence checks. Legacy providers and corporate-action gates stay strict."""

import csv
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .backtest_provider import _at
from .eodhd import read_record, sha
from .market_snapshot import _credentials, _path


def approved(review, run_at):
    try:
        _credentials(review)
        return (
            review["status"] == "approved"
            and isinstance(review["reviewer"], str)
            and bool(review["reviewer"].strip())
            and _at(review["reviewed_at"]) <= run_at
        )
    except (KeyError, TypeError, ValueError):
        return False


def calendar_supported(review, spec, raw_cache, start, end, run_at):
    try:
        if not approved(review, run_at):
            return False
        root = Path(raw_cache).resolve()
        path = _path(root, review["source_file"])
        return (
            review["venue"] == spec["venue"] == "XNYS"
            and review["timezone"] == spec["timezone"] == "America/New_York"
            and review["completeness_reviewed"] is True
            and review["source_reference"].strip()
            and review["license"].strip()
            and _at(review["source_retrieved_at"]) <= _at(review["reviewed_at"]) <= run_at
            and _at(review["coverage_start"]) <= start
            and _at(review["coverage_end"]) >= end
            and review["calendar_sha256"] == spec["snapshot"]["expected_hashes"]["calendar_file"]
            and sha(path.read_bytes()) == review["source_sha256"]
        )
    except (KeyError, TypeError, ValueError, OSError, AttributeError):
        return False


def reconcile_history(
    history, bundle, *, market_root, raw_cache, cutoff, as_of, baseline, action_review, run_at
):
    """Recheck raw/normalized parity; optionally approve cash dividends for price-only research."""
    spec = bundle["spec"]
    zone = ZoneInfo(spec["timezone"])
    records = {k: read_record(raw_cache, v) for k, v in bundle["raw_manifests"].items()}
    if set(records) != {"eod", "splits", "div"}:
        raise ValueError("incomplete raw endpoint set")
    for endpoint, record in records.items():
        req = record["request"]
        if (
            req["endpoint"] != endpoint
            or req["symbol"] != spec["symbol"]
            or not req.get("start")
            or not req.get("end")
            or req["start"] > baseline.astimezone(zone).date().isoformat()
            or req["end"] < as_of.astimezone(zone).date().isoformat()
            or not as_of <= _at(record["retrieved_at"]) <= run_at
        ):
            raise ValueError("raw archive window mismatch")
    raw_prices = {}
    for row in records["eod"]["payload"]:
        day = row["date"]
        if day in raw_prices:
            raise ValueError("duplicate raw price date")
        raw_prices[day] = row
    for bar in history.bars:
        row = raw_prices[bar.at.astimezone(zone).date().isoformat()]
        for field in ("open", "high", "low", "close", "volume"):
            if Decimal(str(row[field])) != getattr(bar, field):
                raise ValueError("raw/normalized price mismatch")
    root = Path(market_root).resolve()
    with _path(root, spec["calendar_file"]).open() as stream:
        sessions = list(csv.DictReader(stream))
    expected = {
        r["timestamp"]: r["end_timestamp"]
        for r in sessions
        if _at(r["timestamp"]) > cutoff and _at(r["end_timestamp"]) <= as_of
    }
    observed = {b.at.isoformat() for b in history.bars}
    missing = sorted(stamp for stamp in expected if stamp not in observed)
    actions, splits = [], []
    for endpoint in ("splits", "div"):
        for index, row in enumerate(records[endpoint]["payload"]):
            at = datetime.combine(datetime.fromisoformat(row["date"]).date(), time.min, zone)
            if not baseline <= at <= as_of:
                continue
            actions.append(
                dict(
                    kind=endpoint,
                    value=row,
                    manifest_sha256=bundle["raw_manifests"][endpoint],
                    payload_pointer=f"/{index}",
                )
            )
            if endpoint == "splits":
                splits.append(row)
    issues = list(history.issues)
    # Every action, including its amount/type/date, must match the normalized action file.
    with _path(root, spec["corporate_actions_file"]).open() as stream:
        normalized = [
            (_at(r["timestamp"]).date().isoformat(), r["type"])
            for r in csv.DictReader(stream)
            if baseline <= _at(r["timestamp"]) <= as_of
        ]
    raw_actions = [
        (a["value"]["date"], "split" if a["kind"] == "splits" else "dividend") for a in actions
    ]
    if sorted(normalized) != sorted(raw_actions):
        raise ValueError("raw/normalized corporate action mismatch")
    reconciled = not actions
    if actions and not splits and approved(action_review, run_at):
        expected_hashes = {k: bundle["raw_manifests"][k] for k in ("splits", "div")}
        reconciled = (
            action_review.get("policy") == "raw_price_only_exclude_cash_dividends"
            and action_review.get("splits_policy") == "block"
            and action_review.get("dividend_cashflows_included") is False
            and action_review.get("raw_manifests") == expected_hashes
        )
    if reconciled:
        issues = [i for i in issues if i != "corporate_action_requires_reconciliation"]
    if splits:
        issues.append("split_price_level_reconciliation_required")
    if missing:
        issues.append("missing_sessions")
    return dict(
        issues=sorted(set(issues)),
        missing_sessions=missing,
        corporate_actions=actions,
        corporate_actions_reconciled=bool(reconciled),
        raw_normalized_integrity="passed",
        scheduled_sessions=len(expected),
        calendar_sha256=spec["snapshot"]["expected_hashes"]["calendar_file"],
        price_return_policy="raw_ohlc; cash dividends excluded; no total-return claim",
    )


def price_path_metrics(bars):
    """Observable close-price drawdown and loss episodes, independent of strategy exposure."""
    result = dict(
        scope="observed_stock_prices; independent of strategy holding period",
        close_price_max_drawdown_pct=None,
        peak_at=None,
        trough_at=None,
        longest_losing_close_episode=None,
        intraday_max_drawdown_pct=None,
    )
    if not bars:
        return result
    entry = peak = bars[0].open
    peak_at = bars[0].at
    worst = Decimal(0)
    longest, current = [], []
    for bar in bars:
        if bar.close > peak:
            peak, peak_at = bar.close, bar.end_at
        drop = 100 * (peak - bar.close) / peak
        if drop > worst:
            worst = drop
            result.update(peak_at=peak_at.isoformat(), trough_at=bar.end_at.isoformat())
        if bar.close < entry:
            current.append(bar)
            if len(current) > len(longest):
                longest = list(current)
        else:
            current = []
    result["close_price_max_drawdown_pct"] = format(worst.normalize(), "f")
    if longest:
        result["longest_losing_close_episode"] = dict(
            start=longest[0].end_at.isoformat(),
            end=longest[-1].end_at.isoformat(),
            sessions=len(longest),
            calendar_days=(longest[-1].at.date() - longest[0].at.date()).days,
            comparison=(
                "completed close below first eligible open; no actual holding-period claim"
            ),
        )
    return result
