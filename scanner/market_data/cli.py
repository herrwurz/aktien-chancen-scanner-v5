"""CLI for controlled Tiingo pilot collection and offline replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from scanner.research_index.repository import ResearchIndex

from .archive import MarketDataArchive
from .expansion import aggregate_batch_reports
from .pilot import (
    build_sec_pilot_index,
    discover_sec_universe_request,
    load_calendar_csv,
    run_tiingo_benchmark,
    run_tiingo_pilot,
    select_us_pilot,
    validate_sec_index_audit,
    write_pilot_report,
)
from .quota import TiingoQuotaLedger


def parser():
    result = argparse.ArgumentParser(prog="python -m scanner.market_data.cli")
    commands = result.add_subparsers(dest="command", required=True)
    index = commands.add_parser("build-sec-pilot-index")
    source = index.add_mutually_exclusive_group(required=True)
    source.add_argument("--sec-universe-request")
    source.add_argument("--sec-cache-root")
    index.add_argument("--index", required=True)
    index.add_argument("--audit-output", required=True)
    pilot = commands.add_parser("pilot")
    pilot.add_argument("--index", required=True)
    pilot.add_argument("--market-db", required=True)
    pilot.add_argument("--raw-cache", required=True)
    pilot.add_argument("--output", required=True)
    pilot.add_argument("--start", required=True)
    pilot.add_argument("--end", required=True)
    pilot.add_argument("--as-of", required=True)
    pilot.add_argument("--count", type=int, default=10)
    pilot.add_argument("--selection-offset", type=int, default=0)
    pilot.add_argument("--correction-lookback-days", type=int, default=0)
    pilot.add_argument("--quota-ledger")
    pilot.add_argument("--max-requests", type=int, default=0)
    pilot.add_argument("--monthly-cost-eur", default="0")
    pilot.add_argument("--max-duration-seconds", type=int, default=120)
    pilot.add_argument("--allow-network", action="store_true")
    pilot.add_argument("--authorize-provider-usage", dest="authorize_usage", action="store_true")
    pilot.add_argument("--calendar")
    pilot.add_argument("--calendar-mics")
    pilot.add_argument("--calendar-timezone")
    pilot.add_argument("--calendar-source-reference")
    pilot.add_argument("--calendar-retrieved-at")
    pilot.add_argument("--sec-index-audit")
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--market-db", required=True)
    benchmark.add_argument("--raw-cache", required=True)
    benchmark.add_argument("--output", required=True)
    benchmark.add_argument("--start", required=True)
    benchmark.add_argument("--end", required=True)
    benchmark.add_argument("--as-of", required=True)
    benchmark.add_argument("--max-requests", type=int, default=0)
    benchmark.add_argument("--monthly-cost-eur", default="0")
    benchmark.add_argument("--correction-lookback-days", type=int, default=0)
    benchmark.add_argument("--quota-ledger")
    benchmark.add_argument("--allow-network", action="store_true")
    benchmark.add_argument(
        "--authorize-provider-usage", dest="authorize_usage", action="store_true"
    )
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--market-db", required=True)
    aggregate.add_argument("--output", required=True)
    aggregate.add_argument("--target-count", type=int, default=100)
    aggregate.add_argument("reports", nargs="+")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "build-sec-pilot-index":
        request = (
            discover_sec_universe_request(args.sec_cache_root)
            if args.sec_cache_root
            else args.sec_universe_request
        )
        audit = build_sec_pilot_index(request, args.index)
        output = Path(args.audit_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(audit, sort_keys=True, separators=(",", ":")) + "\n").encode()
        output.write_bytes(raw)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "index": args.index,
                    "audit": str(output),
                    "audit_sha256": hashlib.sha256(raw).hexdigest(),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "aggregate":
        archive = MarketDataArchive(args.market_db, read_only=True)
        report, paths = aggregate_batch_reports(
            args.reports,
            output_prefix=args.output,
            archive_sha256=archive.logical_sha256(),
            target_count=args.target_count,
        )
        print(json.dumps({"status": report["status"], "sha256": paths["sha256"]}, sort_keys=True))
        return 0
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.utcoffset() is None:
        raise SystemExit("--as-of must include an explicit timezone offset")
    if args.command == "benchmark":
        _reserve_live_quota(args, ["SPY"], datetime.now(UTC))
        report = run_tiingo_benchmark(
            market_archive=MarketDataArchive(args.market_db),
            raw_cache=args.raw_cache,
            start=args.start,
            end=args.end,
            as_of=as_of,
            allow_network=args.allow_network,
            authorize_usage=args.authorize_usage,
            max_requests=args.max_requests,
            monthly_cost_eur=args.monthly_cost_eur,
            correction_lookback_days=args.correction_lookback_days,
        )
        paths = write_pilot_report({**report, "instruments": [report]}, args.output)
        print(json.dumps({"status": report["status"], "sha256": paths["sha256"]}, sort_keys=True))
        return 0
    index = ResearchIndex(args.index)
    if args.allow_network and args.authorize_usage and not args.sec_index_audit:
        raise SystemExit("live pilot requires --sec-index-audit")
    if args.sec_index_audit:
        validate_sec_index_audit(args.sec_index_audit, index, as_of)
    selected = select_us_pilot(index, as_of=as_of, count=args.count, offset=args.selection_offset)
    _reserve_live_quota(args, [row.ticker for row in selected], datetime.now(UTC))
    calendar_values = (
        args.calendar,
        args.calendar_mics,
        args.calendar_timezone,
        args.calendar_source_reference,
        args.calendar_retrieved_at,
    )
    if any(calendar_values) and not all(calendar_values):
        raise SystemExit("all calendar provenance arguments are required together")
    calendar = None
    if all(calendar_values):
        calendar = load_calendar_csv(
            args.calendar,
            supported_mics=args.calendar_mics,
            timezone=args.calendar_timezone,
            source_reference=args.calendar_source_reference,
            retrieved_at=datetime.fromisoformat(args.calendar_retrieved_at),
        )
    report = run_tiingo_pilot(
        index=index,
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
        selection_offset=args.selection_offset,
        correction_lookback_days=args.correction_lookback_days,
        max_duration_seconds=args.max_duration_seconds,
        calendar=calendar,
    )
    paths = write_pilot_report(report, args.output)
    print(
        json.dumps(
            {
                "status": report["status"],
                "json": str(paths["json"]),
                "csv": str(paths["csv"]),
                "sha256_file": str(paths["sha256_file"]),
                "sha256": paths["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def _reserve_live_quota(args, symbols, at):
    live = args.allow_network and args.authorize_usage
    if not live:
        return None
    if not os.getenv("TIINGO_API_TOKEN"):
        return None
    if not args.quota_ledger:
        raise SystemExit("live Tiingo collection requires --quota-ledger")
    return TiingoQuotaLedger(args.quota_ledger).reserve(
        symbols=symbols,
        max_requests=args.max_requests,
        at=at.astimezone(UTC),
    )


if __name__ == "__main__":
    raise SystemExit(main())
