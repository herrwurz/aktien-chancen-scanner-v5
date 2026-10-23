"""Explicit Tiingo collection and offline normalization; never scheduled automatically."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .cli import write_json
from .tiingo import TiingoClient, import_tiingo_file
from .tiingo_adapter import normalize_tiingo_record
from .usage import append_usage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--cache-dir", required=True, type=Path)
    collect.add_argument("--output", required=True, type=Path)
    collect.add_argument("--symbol", required=True)
    collect.add_argument("--from", dest="start", required=True)
    collect.add_argument("--to", dest="end", required=True)
    collect.add_argument("--allow-network", action="store_true")
    collect.add_argument("--authorize-provider-usage", action="store_true")
    collect.add_argument("--max-requests", type=int, default=0)
    collect.add_argument("--monthly-total-eur", default="0")
    replay = commands.add_parser("replay")
    replay.add_argument("--cache-dir", required=True, type=Path)
    replay.add_argument("--manifest-sha256", required=True)
    replay.add_argument("--output", required=True, type=Path)
    offline = commands.add_parser("import")
    offline.add_argument("--input", required=True, type=Path)
    offline.add_argument("--cache-dir", required=True, type=Path)
    offline.add_argument("--output", required=True, type=Path)
    offline.add_argument("--symbol", required=True)
    offline.add_argument("--from", dest="start", required=True)
    offline.add_argument("--to", dest="end", required=True)
    offline.add_argument("--retrieved-at", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "replay":
            write_json(args.output, normalize_tiingo_record(args.cache_dir, args.manifest_sha256))
            print(json.dumps({"status": "offline_normalized"}))
            return 0
        if args.command == "import":
            record = import_tiingo_file(
                args.input,
                args.cache_dir,
                symbol=args.symbol,
                start=args.start,
                end=args.end,
                retrieved_at=datetime.fromisoformat(args.retrieved_at),
            )
            write_json(
                args.output, {"manifest_sha256": record["manifest_sha256"], "attempted_requests": 0}
            )
            print(json.dumps({"status": "offline_imported", "requests": 0}))
            return 0
        client = TiingoClient(
            args.cache_dir,
            allow_network=args.allow_network,
            authorize_usage=args.authorize_provider_usage,
            max_requests=args.max_requests,
            monthly_cost_eur=args.monthly_total_eur,
        )
        event = {
            "at": datetime.now(UTC).isoformat(),
            "provider": "Tiingo",
            "symbol": args.symbol,
            "start": args.start,
            "end": args.end,
            "monthly_total_declared_eur": args.monthly_total_eur,
            "cost_eur": None,
        }
        append_usage(args.cache_dir / "usage.jsonl", dict(event, status="started"))
        try:
            record = client.fetch(args.symbol, start=args.start, end=args.end)
        except Exception as exc:
            append_usage(
                args.cache_dir / "usage.jsonl",
                dict(
                    event,
                    status="error",
                    error=type(exc).__name__,
                    attempted_requests=client.attempted_requests,
                ),
            )
            raise
        append_usage(
            args.cache_dir / "usage.jsonl",
            dict(
                event,
                status="completed",
                attempted_requests=client.attempted_requests,
                manifest_sha256=record["manifest_sha256"],
            ),
        )
        write_json(
            args.output,
            {
                "manifest_sha256": record["manifest_sha256"],
                "attempted_requests": client.attempted_requests,
            },
        )
        print(json.dumps({"status": "collected", "requests": client.attempted_requests}))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
