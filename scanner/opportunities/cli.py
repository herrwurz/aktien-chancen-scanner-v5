"""Offline, read-only CLI for V2.5.2 short-term opportunity research."""

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

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


def _load_pilot_coverage(path_value: str) -> dict:
    path = Path(path_value).resolve()
    raw = path.read_bytes()
    sidecar = path.with_suffix(".sha256")
    expected = hashlib.sha256(raw).hexdigest()
    try:
        entries = {
            name: digest
            for line in sidecar.read_text(encoding="ascii").splitlines()
            if len(parts := line.split(maxsplit=1)) == 2
            for digest, name in [parts]
        }
    except (OSError, UnicodeError):
        raise ValueError("pilot coverage SHA sidecar unavailable") from None
    if entries.get(path.name) != expected:
        raise ValueError("pilot coverage SHA mismatch")
    value = json.loads(raw)
    value["coverage_report_sha256"] = expected
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-index", required=True)
    parser.add_argument("--market-archive", required=True)
    parser.add_argument(
        "--as-of",
        required=True,
        help="Aware archive retrieval cutoff or deterministic 'archive-latest'",
    )
    parser.add_argument("--signal-date", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--benchmark-asset-id")
    parser.add_argument("--pilot-coverage")
    parser.add_argument("--instrument-reviews")
    parser.add_argument("--minimum-liquidity", type=_positive_decimal, default=Decimal("1000000"))
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    archive = MarketDataArchive(args.market_archive, read_only=True)
    if args.as_of == "archive-latest":
        as_of = archive.latest_storage_time()
    else:
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        if as_of.tzinfo is None:
            raise ValueError("--as-of must include a timezone")
    pilot_coverage = None
    if args.pilot_coverage:
        pilot_coverage = _load_pilot_coverage(args.pilot_coverage)
    instrument_reviews = None
    if args.instrument_reviews:
        review_raw = Path(args.instrument_reviews).read_bytes()
        instrument_reviews = json.loads(review_raw)
        instrument_reviews["file_sha256"] = hashlib.sha256(review_raw).hexdigest()
    report = run_dry_run(
        ResearchIndex(args.research_index),
        archive,
        as_of=as_of,
        signal_date=date.fromisoformat(args.signal_date),
        benchmark_asset_id=args.benchmark_asset_id,
        minimum_liquidity=args.minimum_liquidity,
        pilot_coverage=pilot_coverage,
        instrument_reviews=instrument_reviews,
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
