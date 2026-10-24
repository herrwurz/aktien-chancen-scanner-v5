"""CLI for controlled Tiingo pilot collection and offline replay."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from scanner.research_index.repository import ResearchIndex

from .archive import MarketDataArchive
from .pilot import run_tiingo_pilot, write_pilot_report


def parser():
    result = argparse.ArgumentParser(prog="python -m scanner.market_data.cli")
    commands = result.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot")
    pilot.add_argument("--index", required=True)
    pilot.add_argument("--market-db", required=True)
    pilot.add_argument("--raw-cache", required=True)
    pilot.add_argument("--output", required=True)
    pilot.add_argument("--start", required=True)
    pilot.add_argument("--end", required=True)
    pilot.add_argument("--as-of", required=True)
    pilot.add_argument("--count", type=int, default=10)
    pilot.add_argument("--max-requests", type=int, default=0)
    pilot.add_argument("--monthly-cost-eur", default="0")
    pilot.add_argument("--allow-network", action="store_true")
    pilot.add_argument("--authorize-provider-usage", dest="authorize_usage", action="store_true")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.utcoffset() is None:
        raise SystemExit("--as-of must include an explicit timezone offset")
    report = run_tiingo_pilot(
        index=ResearchIndex(args.index),
        market_archive=MarketDataArchive(args.market_db),
        raw_cache=args.raw_cache,
        start=args.start,
        end=args.end,
        as_of=as_of,
        allow_network=args.allow_network,
        authorize_usage=args.authorize_usage,
        max_requests=args.max_requests,
        monthly_cost_eur=args.monthly_cost_eur,
        count=args.count,
    )
    paths = write_pilot_report(report, args.output)
    print(
        json.dumps(
            {
                "status": report["status"],
                "json": str(paths["json"]),
                "csv": str(paths["csv"]),
                "sha256": paths["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
