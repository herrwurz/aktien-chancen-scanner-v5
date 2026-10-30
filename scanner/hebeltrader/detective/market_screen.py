"""Market-data screen: rank universe stocks whose chart matches the teaser's chart clues.

Evidence-free hypotheses only: a chart match never identifies a stock. Snapshots are
exported once with network access (``python -m ...market_screen export OUT.json``) and
ranked offline, so a ranking can be frozen before any solution is known.
"""

import json
import os
import re
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

from .chart_check import chart_score, trend_features
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


def rank(text, snapshots, *, universe=None, limit=8, sector_filter=True):
    """Rank universe assets with a snapshot; the sector filter applies only if a sector is named."""
    clues = teaser_chart_clues(text)
    sectors = sectors_in(text) if sector_filter else []
    ranked = []
    for asset in universe if universe is not None else load_universe():
        ticker = asset.get("ticker")
        features = snapshots.get(ticker) if ticker else None
        if not features or (sectors and asset["sector"] not in sectors):
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

    fetch = fetch or fetch_closes
    as_of = today or date.today()
    assets = list(universe if universe is not None else load_universe())
    tickers = []
    seen = set()
    for asset in assets:
        ticker = asset.get("ticker")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)

    token_present = bool(os.environ.get("EODHD_API_TOKEN"))
    # Custom fetch callables (tests) do not require a live token.
    live_fetch = fetch is fetch_closes
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


def main(argv):
    if not argv or argv[0] != "export" or len(argv) < 2:
        print(
            "usage: python -m scanner.hebeltrader.detective.market_screen "
            "export OUT.json [--as-of YYYY-MM-DD]",
            file=sys.stderr,
        )
        return 2
    out = Path(argv[1])
    as_of = None
    if len(argv) == 4 and argv[2] == "--as-of":
        as_of = date.fromisoformat(argv[3])
    elif len(argv) != 2:
        print(
            "usage: python -m scanner.hebeltrader.detective.market_screen "
            "export OUT.json [--as-of YYYY-MM-DD]",
            file=sys.stderr,
        )
        return 2

    def progress(index, total, ticker):
        print(f"[{index}/{total}] {ticker}", file=sys.stderr)

    payload = export_snapshots(today=as_of, progress=progress)
    meta = payload["export_meta"]
    if meta["status"] == "missing_token":
        print("EODHD_API_TOKEN is not set; refusing live export.", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"{meta['succeeded']}/{meta['attempted']} snapshots written to {out} "
        f"(status={meta['status']})"
    )
    return 0 if meta["succeeded"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
