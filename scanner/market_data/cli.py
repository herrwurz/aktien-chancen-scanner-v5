"""CLI for controlled Tiingo pilot collection and offline replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from scanner.research_index.repository import ResearchIndex

from .archive import MarketDataArchive
from .pilot import (
    build_sec_pilot_index,
    load_calendar_csv,
    run_tiingo_pilot,
    write_pilot_report,
)


def parser():
    result = argparse.ArgumentParser(prog="python -m scanner.market_data.cli")
    commands = result.add_subparsers(dest="command", required=True)
    index = commands.add_parser("build-sec-pilot-index")
    index.add_argument("--sec-universe-request", required=True)
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
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "build-sec-pilot-index":
        audit = build_sec_pilot_index(args.sec_universe_request, args.index)
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
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.utcoffset() is None:
        raise SystemExit("--as-of must include an explicit timezone offset")
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


if __name__ == "__main__":
    raise SystemExit(main())
