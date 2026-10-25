"""Offline, read-only CLI for V2.5.2 short-term opportunity research."""

import argparse
import json
from datetime import date, datetime
from decimal import Decimal

from scanner.market_data.archive import MarketDataArchive
from scanner.opportunities.report import run_dry_run, write_report
from scanner.research_index.repository import ResearchIndex


def _positive_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise argparse.ArgumentTypeError("must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-index", required=True)
    parser.add_argument("--market-archive", required=True)
    parser.add_argument("--as-of", required=True, help="Aware archive retrieval cutoff")
    parser.add_argument("--signal-date", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--benchmark-asset-id")
    parser.add_argument("--minimum-liquidity", type=_positive_decimal, default=Decimal("1000000"))
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    report = run_dry_run(
        ResearchIndex(args.research_index),
        MarketDataArchive(args.market_archive, read_only=True),
        as_of=as_of,
        signal_date=date.fromisoformat(args.signal_date),
        benchmark_asset_id=args.benchmark_asset_id,
        minimum_liquidity=args.minimum_liquidity,
    )
    artifacts = write_report(report, args.output)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "coverage": report["coverage"],
                "artifacts": artifacts,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
