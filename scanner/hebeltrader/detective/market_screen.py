"""Market-data screen: rank universe stocks whose chart matches the teaser's chart clues.

Evidence-free hypotheses only: a chart match never identifies a stock. Snapshots are
exported once with network access (``python -m ...market_screen export OUT.json``) and
ranked offline, so a ranking can be frozen before any solution is known.
"""

import json
import re
import sys
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


def export_snapshots(*, universe=None, fetch=None, today=None):
    """Fetch closes per universe ticker; ``fetch(ticker)`` returns closes or None."""
    from .chart_check import fetch_closes

    fetch = fetch or fetch_closes
    snapshots = {}
    for asset in universe if universe is not None else load_universe():
        ticker = asset.get("ticker")
        if not ticker or ticker in snapshots:
            continue
        features = trend_features(fetch(ticker) or [])
        if features:
            snapshots[ticker] = features
    return {
        "as_of": (today or date.today()).isoformat(),
        "exported_at": datetime.now(UTC).isoformat(),
        "snapshots": snapshots,
    }


def main(argv):
    if len(argv) != 2 or argv[0] != "export":
        print("usage: python -m scanner.hebeltrader.detective.market_screen export OUT.json")
        return 2
    payload = export_snapshots()
    Path(argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{len(payload['snapshots'])} snapshots written to {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
