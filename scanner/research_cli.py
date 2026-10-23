"""Read-only CLI for controlled research-provider snapshots."""

import argparse
import json
import os
from pathlib import Path

from scanner.research import AssetIdentity
from scanner.research_providers.sec_edgar import (
    SecEdgarClient,
    SecEventProvider,
    SecUniverseProvider,
)
from scanner.research_service import ResearchService


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sec-universe")
    events = subparsers.add_parser("sec-events")
    events.add_argument("--cik", required=True)
    events.add_argument("--name", required=True)
    events.add_argument("--ticker", required=True)
    return parser


def run(argv=None):
    args = _parser().parse_args(argv)
    client = SecEdgarClient(
        args.cache_dir,
        user_agent=os.getenv("SEC_USER_AGENT"),
        allow_network=args.allow_network,
        max_requests=args.max_requests,
        dry_run=args.dry_run,
    )
    if args.command == "sec-universe":
        result = ResearchService(universe_provider=SecUniverseProvider(client)).universe()
    else:
        identity = AssetIdentity(
            asset_type="stock",
            name=args.name,
            ticker=args.ticker,
            cik=args.cik,
            country="US",
            quality_status="incomplete",
            source_id="operator-input",
        )
        result = ResearchService(
            universe_provider=SecUniverseProvider(client),
            event_provider=SecEventProvider(client),
        ).events(identity)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = result["provider_status"]["status"]
    return 2 if status == "unavailable" else 0


def main():
    raise SystemExit(run())


if __name__ == "__main__":
    main()
