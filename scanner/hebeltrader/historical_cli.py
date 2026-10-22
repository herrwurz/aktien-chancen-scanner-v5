"""Explicit V1.5 commands: optional authorized collection, offline conversion/audit."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from scanner.db import create_db, create_sessions

from .cli import write_json
from .config import ImportSettings
from .eodhd import ENDPOINTS, EodhdClient
from .eodhd_adapter import prepare_snapshot
from .historical_pipeline import build_pipeline_report, write_audit


def _load(path, default):
    return json.loads(Path(path).read_text()) if path else default


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--cache-dir", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--symbol", required=True)
    collect.add_argument("--from", dest="start")
    collect.add_argument("--to", dest="end")
    collect.add_argument(
        "--endpoints", nargs="+", choices=sorted(ENDPOINTS), default=["eod", "splits", "div"]
    )
    collect.add_argument("--delisted", action="store_true")
    collect.add_argument("--allow-network", action="store_true")
    collect.add_argument("--authorize-provider-usage", action="store_true")
    collect.add_argument("--max-requests", type=int, default=0)
    collect.add_argument("--monthly-total-eur", default="0")
    collect.add_argument("--max-api-units", type=int)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("--cache-dir", type=Path, required=True)
    normalize.add_argument("--raw-manifests", type=Path, required=True)
    normalize.add_argument("--spec", type=Path, required=True)
    normalize.add_argument("--calendar", type=Path, required=True)
    normalize.add_argument("--data-root", type=Path, required=True)
    normalize.add_argument("--run-at", required=True)
    normalize.add_argument("--output", type=Path, required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--run-at", required=True)
    audit.add_argument("--as-of", required=True)
    audit.add_argument("--output-prefix", type=Path, required=True)
    audit.add_argument("--openfigi", type=Path)
    audit.add_argument("--openfigi-cache", type=Path)
    audit.add_argument("--historical-sources", type=Path)
    audit.add_argument("--map", type=Path)
    audit.add_argument("--rules", type=Path)
    audit.add_argument("--bundles", type=Path, nargs="*", default=[])
    audit.add_argument("--data-root", type=Path)
    audit.add_argument("--eodhd-cache", type=Path)
    audit.add_argument("--expected-count", type=int, default=118)
    audit.add_argument("--analysis-mode", choices=["research", "verified"], default="research")
    audit.add_argument("--reported-openfigi-hits", type=int)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command in {"collect", "normalize"} and os.path.lexists(args.output):
            raise ValueError("output exists; nothing requested or overwritten")
        if args.command == "collect":
            provider = EodhdClient(
                args.cache_dir,
                allow_network=args.allow_network,
                authorize_usage=args.authorize_provider_usage,
                max_requests=args.max_requests,
                max_api_units=args.max_api_units,
                monthly_cost_eur=args.monthly_total_eur,
            )
            records = {
                endpoint: provider.fetch(
                    endpoint, args.symbol, start=args.start, end=args.end, delisted=args.delisted
                )["manifest_sha256"]
                for endpoint in args.endpoints
            }
            write_json(
                args.output,
                dict(
                    raw_manifests=records,
                    attempted_requests=provider.attempted_requests,
                    api_units_spent=provider.api_units_spent,
                ),
            )
            print(json.dumps(dict(status="collected", requests=provider.attempted_requests)))
        elif args.command == "normalize":
            manifests = _load(args.raw_manifests, {})
            bundle = prepare_snapshot(
                args.cache_dir,
                args.data_root,
                records=manifests.get("raw_manifests", manifests),
                spec=_load(args.spec, {}),
                calendar_path=args.calendar,
                run_at=datetime.fromisoformat(args.run_at),
            )
            write_json(args.output, bundle)
            print(
                json.dumps(
                    dict(status="normalized", snapshot=bundle["spec"]["snapshot"]["version"])
                )
            )
        else:
            records = []
            for path in (args.openfigi, args.historical_sources):
                value = _load(path, [])
                records.extend(value["records"] if isinstance(value, dict) else value)
            engine = create_db(ImportSettings())
            with create_sessions(engine)() as session:
                session.execute(
                    text(
                        "SET TRANSACTION READ ONLY"
                        if engine.dialect.name == "postgresql"
                        else "PRAGMA query_only=ON"
                    )
                )
                report = build_pipeline_report(
                    session,
                    run_at=datetime.fromisoformat(args.run_at),
                    as_of=datetime.fromisoformat(args.as_of),
                    records=records,
                    cache_dir=args.openfigi_cache,
                    mapping=_load(args.map, {}),
                    rules=_load(args.rules, {}),
                    bundles=[_load(p, {}) for p in args.bundles],
                    market_root=args.data_root,
                    raw_cache=args.eodhd_cache,
                    expected_count=args.expected_count,
                    analysis_mode=args.analysis_mode,
                    reported_openfigi_hits=args.reported_openfigi_hits,
                )
                write_audit(args.output_prefix, report)
            print(json.dumps(report["pipeline_summary"], sort_keys=True))
            return 2 if report["warnings"] else 0
        return 0
    except Exception as exc:
        # Never emit HTTP exception messages: authenticated URLs can contain tokens.
        print(json.dumps(dict(status="error", error=type(exc).__name__)), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
