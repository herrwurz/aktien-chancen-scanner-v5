"""Market-data screen: rank universe stocks whose chart matches the teaser's chart clues.

Evidence-free hypotheses only: a chart match never identifies a stock. Snapshots are
exported once with network access (``python -m ...market_screen export OUT.json``) and
ranked offline, so a ranking can be frozen before any solution is known.

Point-in-time (PIT): ``export-pit`` builds ``by_as_of`` features from one bar pull per
ticker so each case can use closes ≤ its ``publication_date`` only.
"""

import json
import os
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .chart_check import chart_score, closes_through, trend_features
from .research_plan import stock_text
from .structure_screen import load_universe, sectors_in

CLUES = (
    (
        "above_gd200",
        r"200[\s-]*tage[\s-]*linie\s+(?:\w+\s+){0,2}(?:zurückerobert|verteidigt|überwunden)",
    ),
    ("breakout", r"ausbruch|befreiungsschlag|rallye|rally|kaufsignal"),
    ("correction", r"korrektur|rücksetzer|konsolidierung"),
    ("steady_uptrend", r"seit\s+jahren\s+(?:\w+\s+)?(?:kontinuierlich\s+)?nach\s+oben"),
)

PIT_FORMAT = "hebeltrader-market-snapshots-pit-v1"


def teaser_chart_clues(text):
    clean = stock_text(text)
    return [name for name, pattern in CLUES if re.search(pattern, clean, re.I)]


def match_score(features, clues):
    """Teaser-conditioned score: base trend score plus clue-specific adjustments."""
    if not features:
        return 0
    score = chart_score(features)
    if "above_gd200" in clues:
        score += 6 if features["above_gd200"] else -6
    if "breakout" in clues and features["breakout"]:
        score += 3
    if "correction" in clues and features["near_high_pct"] < -5:
        score += 2
    if "steady_uptrend" in clues and features["return_1y_pct"] > 15 and features["gd200_rising"]:
        score += 4
    return score


def rank(text, snapshots, *, universe=None, limit=8, sector_filter=True, blocked=None):
    """Rank universe assets with a snapshot; the sector filter applies only if a sector is named."""
    from .featured_calls import is_blocked

    clues = teaser_chart_clues(text)
    sectors = sectors_in(text) if sector_filter else []
    ranked = []
    for asset in universe if universe is not None else load_universe():
        ticker = asset.get("ticker")
        features = snapshots.get(ticker) if ticker else None
        if not features or (sectors and asset["sector"] not in sectors):
            continue
        if is_blocked(asset, blocked):
            continue
        ranked.append(
            {
                "name": asset["name"],
                "ticker": ticker,
                "sector": asset["sector"],
                "layer": asset.get("layer"),
                "structure": asset.get("structure"),
                "score": match_score(features, clues),
                "features": features,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["name"]))
    return {
        "clues": clues,
        "sectors": sectors,
        "snapshot_coverage": len(snapshots),
        "ranked_before_limit": len(ranked),
        "ranking": ranked[:limit],
    }


def _universe_tickers(universe):
    tickers = []
    seen = set()
    for asset in universe:
        ticker = asset.get("ticker")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def export_snapshots(
    *,
    universe=None,
    fetch=None,
    today=None,
    pause_seconds=0.15,
    progress=None,
):
    """Fetch closes per universe ticker; ``fetch(ticker)`` returns closes or None.

    Returns a payload with ``snapshots`` plus ``export_meta`` describing coverage and
    failures. Missing ``EODHD_API_TOKEN`` (when using the live fetcher) is recorded in
    meta and yields empty snapshots rather than inventing prices.
    """
    from .chart_check import fetch_closes

    as_of = today or date.today()
    if fetch is None:

        def fetch(ticker):
            return fetch_closes(ticker, today=as_of)

        live_fetch = True
    else:
        live_fetch = False

    assets = list(universe if universe is not None else load_universe())
    tickers = _universe_tickers(assets)

    token_present = bool(os.environ.get("EODHD_API_TOKEN"))
    if live_fetch and not token_present:
        return {
            "as_of": as_of.isoformat(),
            "exported_at": datetime.now(UTC).isoformat(),
            "snapshots": {},
            "export_meta": {
                "status": "missing_token",
                "token_present": False,
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "insufficient_history": 0,
                "universe_tickers": len(tickers),
                "failures": [],
            },
        }

    snapshots = {}
    failures = []
    insufficient = 0
    for index, ticker in enumerate(tickers, 1):
        if progress is not None:
            progress(index, len(tickers), ticker)
        closes = fetch(ticker) or []
        if not closes:
            failures.append({"ticker": ticker, "reason": "fetch_empty_or_error"})
            if pause_seconds and live_fetch:
                time.sleep(pause_seconds)
            continue
        features = trend_features(closes)
        if not features:
            insufficient += 1
            failures.append({"ticker": ticker, "reason": "insufficient_history"})
        else:
            snapshots[ticker] = features
        if pause_seconds and live_fetch:
            time.sleep(pause_seconds)

    succeeded = len(snapshots)
    status = "ok" if succeeded else "no_snapshots"
    if failures and succeeded:
        status = "partial"
    return {
        "as_of": as_of.isoformat(),
        "exported_at": datetime.now(UTC).isoformat(),
        "snapshots": snapshots,
        "export_meta": {
            "status": status,
            "token_present": token_present if live_fetch else None,
            "attempted": len(tickers),
            "succeeded": succeeded,
            "failed": len(failures) - insufficient,
            "insufficient_history": insufficient,
            "universe_tickers": len(tickers),
            "failures": failures,
        },
    }


def features_by_as_of(bars_by_ticker, as_of_dates):
    """Build ``{as_of: {ticker: features}}`` from dated bars (offline, no network)."""
    by_as_of = {}
    for raw in sorted({str(d)[:10] for d in as_of_dates}):
        snapshots = {}
        for ticker, bars in bars_by_ticker.items():
            closes = closes_through(bars, raw)
            features = trend_features(closes or [])
            if features:
                snapshots[ticker] = features
        by_as_of[raw] = {
            "as_of": raw,
            "snapshot_coverage": len(snapshots),
            "snapshots": snapshots,
        }
    return by_as_of


def export_pit_snapshots(
    as_of_dates,
    *,
    universe=None,
    fetch_bars=None,
    pause_seconds=0.15,
    progress=None,
    history_pad_days=420,
):
    """One bar pull per ticker through max(as_of); features sliced per publication date.

    ``pit_basis`` is calendar ``publication_date`` EOD (last close on or before that day).
    This is coarser than ``publication_at`` and must not be treated as an exact cutoff for
    evidence packets.
    """
    from .chart_check import fetch_eod_bars

    dates = sorted({str(d)[:10] for d in as_of_dates if d})
    if not dates:
        raise ValueError("export_pit_snapshots requires at least one as_of date")
    min_as_of = date.fromisoformat(dates[0])
    max_as_of = date.fromisoformat(dates[-1])
    from_date = min_as_of - timedelta(days=history_pad_days)

    assets = list(universe if universe is not None else load_universe())
    tickers = _universe_tickers(assets)
    token_present = bool(os.environ.get("EODHD_API_TOKEN"))
    live_fetch = fetch_bars is None
    if live_fetch and not token_present:
        return {
            "format": PIT_FORMAT,
            "pit_basis": "publication_date_eod",
            "exported_at": datetime.now(UTC).isoformat(),
            "as_of_dates": dates,
            "by_as_of": {},
            "export_meta": {
                "status": "missing_token",
                "token_present": False,
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "universe_tickers": len(tickers),
                "failures": [],
                "from_date": from_date.isoformat(),
                "to_date": max_as_of.isoformat(),
            },
        }

    fetch_bars = fetch_bars or (
        lambda ticker: fetch_eod_bars(ticker, from_date=from_date, to_date=max_as_of)
    )

    bars_by_ticker = {}
    failures = []
    for index, ticker in enumerate(tickers, 1):
        if progress is not None:
            progress(index, len(tickers), ticker)
        bars = fetch_bars(ticker)
        if not bars:
            failures.append({"ticker": ticker, "reason": "fetch_empty_or_error"})
        else:
            bars_by_ticker[ticker] = bars
        if pause_seconds and live_fetch:
            time.sleep(pause_seconds)

    by_as_of = features_by_as_of(bars_by_ticker, dates)
    coverages = [bucket["snapshot_coverage"] for bucket in by_as_of.values()]
    status = "ok" if bars_by_ticker and not failures else "no_snapshots"
    if bars_by_ticker and failures:
        status = "partial"
    return {
        "format": PIT_FORMAT,
        "pit_basis": "publication_date_eod",
        "exported_at": datetime.now(UTC).isoformat(),
        "as_of_dates": dates,
        "by_as_of": by_as_of,
        # Convenience view: latest as_of bucket (compatible helpers / diagnose).
        "as_of": dates[-1],
        "snapshots": by_as_of[dates[-1]]["snapshots"],
        "export_meta": {
            "status": status,
            "token_present": token_present if live_fetch else None,
            "attempted": len(tickers),
            "succeeded": len(bars_by_ticker),
            "failed": len(failures),
            "universe_tickers": len(tickers),
            "failures": failures,
            "from_date": from_date.isoformat(),
            "to_date": max_as_of.isoformat(),
            "min_coverage": min(coverages) if coverages else 0,
            "max_coverage": max(coverages) if coverages else 0,
        },
    }


def resolve_case_snapshots(snapshot_payload, publication_date):
    """Pick the snapshot map for one case; refuse post-publication single-as_of leakage."""
    if snapshot_payload.get("format") == PIT_FORMAT or "by_as_of" in snapshot_payload:
        if not publication_date:
            return {
                "snapshots": None,
                "snapshot_as_of": None,
                "status": "no_publication_date_for_pit",
            }
        key = str(publication_date)[:10]
        bucket = (snapshot_payload.get("by_as_of") or {}).get(key)
        if not bucket:
            return {
                "snapshots": None,
                "snapshot_as_of": key,
                "status": "pit_as_of_missing",
            }
        snaps = bucket.get("snapshots") or {}
        if not snaps:
            return {
                "snapshots": None,
                "snapshot_as_of": bucket.get("as_of", key),
                "status": "insufficient_history_at_as_of",
                "snapshot_coverage": 0,
                "pit_basis": snapshot_payload.get("pit_basis", "publication_date_eod"),
            }
        return {
            "snapshots": snaps,
            "snapshot_as_of": bucket.get("as_of", key),
            "status": "ok",
            "snapshot_coverage": bucket.get("snapshot_coverage", len(snaps)),
            "pit_basis": snapshot_payload.get("pit_basis", "publication_date_eod"),
        }

    snapshots = snapshot_payload.get("snapshots")
    if snapshots is None:
        raise ValueError("snapshots file must contain a snapshots object")
    as_of = snapshot_payload.get("as_of")
    if publication_date and as_of and str(as_of)[:10] > str(publication_date)[:10]:
        return {
            "snapshots": None,
            "snapshot_as_of": as_of,
            "status": "snapshot_as_of_after_publication",
        }
    return {
        "snapshots": snapshots,
        "snapshot_as_of": as_of,
        "status": "ok",
        "snapshot_coverage": len(snapshots),
    }


def as_of_dates_from_inputs(inputs_path):
    payload = json.loads(Path(inputs_path).read_text(encoding="utf-8"))
    return sorted(
        {
            str(case["publication_date"])[:10]
            for case in payload["cases"]
            if case.get("publication_date")
        }
    )


def main(argv):
    usage = (
        "usage:\n"
        "  python -m scanner.hebeltrader.detective.market_screen "
        "export OUT.json [--as-of YYYY-MM-DD]\n"
        "  python -m scanner.hebeltrader.detective.market_screen "
        "export-pit OUT.json --inputs INPUTS.json"
    )
    if not argv:
        print(usage, file=sys.stderr)
        return 2

    def progress(index, total, ticker):
        print(f"[{index}/{total}] {ticker}", file=sys.stderr)

    if argv[0] == "export":
        if len(argv) < 2:
            print(usage, file=sys.stderr)
            return 2
        out = Path(argv[1])
        as_of = None
        if len(argv) == 4 and argv[2] == "--as-of":
            as_of = date.fromisoformat(argv[3])
        elif len(argv) != 2:
            print(usage, file=sys.stderr)
            return 2
        payload = export_snapshots(today=as_of, progress=progress)
    elif argv[0] == "export-pit":
        if len(argv) != 4 or argv[2] != "--inputs":
            print(usage, file=sys.stderr)
            return 2
        out = Path(argv[1])
        dates = as_of_dates_from_inputs(argv[3])
        if not dates:
            print("no publication_date values in inputs", file=sys.stderr)
            return 1
        payload = export_pit_snapshots(dates, progress=progress)
    else:
        print(usage, file=sys.stderr)
        return 2

    meta = payload["export_meta"]
    if meta["status"] == "missing_token":
        print("EODHD_API_TOKEN is not set; refusing live export.", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if "by_as_of" in payload:
        print(
            f"PIT {meta['succeeded']}/{meta['attempted']} tickers, "
            f"{len(payload['as_of_dates'])} as_of dates → {out} "
            f"(status={meta['status']}, coverage "
            f"{meta.get('min_coverage')}-{meta.get('max_coverage')})"
        )
    else:
        print(
            f"{meta['succeeded']}/{meta['attempted']} snapshots written to {out} "
            f"(status={meta['status']})"
        )
    return 0 if meta["succeeded"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
