"""Primary HEBELTRADER workflow; all network access and monitoring are opt-in."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from .history import evaluate_frozen, inventory_history
from .investigation import InvestigationRequest, Investigator
from .monitor import TeaserMonitor
from .public_web import PublicWebResearch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyze", "watch", "inventory", "evaluate"])
    parser.add_argument("--root", type=Path, default=Path("data/hebeltrader-detective"))
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--headline", default="")
    parser.add_argument("--publisher", default="")
    parser.add_argument("--publication-at")
    parser.add_argument(
        "--packet", type=Path, help="Operator-supplied source documents; not a blind benchmark"
    )
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--historical-blind", action="store_true")
    parser.add_argument("--max-requests", type=int, default=40)
    parser.add_argument("--primary-domains", type=Path)
    parser.add_argument("--product-issuers", type=Path)
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--query", action="append")
    parser.add_argument(
        "--history", type=Path, default=Path("docs/hebeltrader-identification-rules.md")
    )
    parser.add_argument("--rankings", type=Path)
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args(argv)
    if args.command == "inventory":
        print(json.dumps(inventory_history(args.history), ensure_ascii=False, indent=2))
        return 0
    if args.command == "evaluate":
        if not args.rankings or not args.labels:
            parser.error("evaluate needs --rankings and --labels, after a frozen scan")
        print(json.dumps(evaluate_frozen(args.rankings, args.labels), ensure_ascii=False, indent=2))
        return 0
    if args.labels:
        parser.error("labels are forbidden during analysis")
    if not 1 <= args.max_requests <= 100 or args.interval_seconds < 300:
        parser.error("bounded requests 1..100 and polling interval >=300 seconds required")
    while True:
        domains = json.loads(args.primary_domains.read_text()) if args.primary_domains else {}
        web = PublicWebResearch(
            args.root / "sources",
            allow_network=args.allow_network,
            max_requests=args.max_requests,
            primary_domains=domains,
        )
        issuers = json.loads(args.product_issuers.read_text()) if args.product_issuers else {}
        engine = Investigator(
            args.root, web=web if args.allow_network else None, product_issuers=issuers
        )
        if args.command == "analyze":
            request = InvestigationRequest(
                teaser_text=args.text_file.read_text() if args.text_file else "",
                teaser_url=args.url,
                headline=args.headline,
                publisher=args.publisher,
                publication_at=datetime.fromisoformat(args.publication_at)
                if args.publication_at
                else None,
            )
            packet = json.loads(args.packet.read_text()) if args.packet else None
            result = engine.analyze(
                request, documents=packet, historical_blind=args.historical_blind
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if not args.allow_network:
            parser.error("watch needs explicit --allow-network; never starts implicitly")
        monitor = TeaserMonitor(args.root, web=web, engine=engine, queries=args.query)
        print(json.dumps(monitor.scan_once(), ensure_ascii=False), flush=True)
        if args.once:
            return 0
        for _ in range(args.interval_seconds):
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
