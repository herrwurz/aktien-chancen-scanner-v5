"""Primary HEBELTRADER workflow; all network access and monitoring are opt-in."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from .case_journal import CaseJournal
from .history import evaluate_frozen, inventory_history
from .investigation import InvestigationRequest, Investigator
from .monitor import TeaserMonitor
from .public_web import PublicWebResearch
from .publisher_catalog import CATALOG_URL
from .resolution import ResolutionRequest
from .workflow import run_case


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "analyze",
            "watch",
            "inventory",
            "evaluate",
            "cases",
            "resolve",
            "quality",
            "register",
        ],
    )
    parser.add_argument("--root", type=Path, default=Path("data/hebeltrader-detective"))
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--original-source-url")
    parser.add_argument("--source-retrieved-at")
    parser.add_argument("--headline", default="")
    parser.add_argument("--publisher", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--issue", default="")
    parser.add_argument(
        "--evaluation-class",
        choices=["unclassified", "development_regression", "retrospective", "prospective_blind"],
        default="unclassified",
    )
    parser.add_argument("--new-blind-case", action="store_true")
    parser.add_argument("--discovery-feed", action="append")
    parser.add_argument("--case-id")
    parser.add_argument("--resolution-file", type=Path)
    parser.add_argument(
        "--register-path", type=Path, default=Path("docs/hebeltrader-identification-rules.md")
    )
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
        "--no-catalog", action="store_true", help="Use only the existing RSS/search path"
    )
    parser.add_argument("--catalog-limit", type=int, default=3, choices=range(1, 11))
    parser.add_argument(
        "--history", type=Path, default=Path("docs/hebeltrader-identification-rules.md")
    )
    parser.add_argument("--rankings", type=Path)
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args(argv)
    if args.command in ("cases", "resolve", "quality", "register"):
        journal = CaseJournal(args.root / "cases")
        if args.command == "resolve":
            if not args.case_id or not args.resolution_file:
                parser.error("resolve needs --case-id and --resolution-file")
            resolution = ResolutionRequest.model_validate_json(args.resolution_file.read_text())
            result = journal.resolve(args.case_id, resolution.model_dump(exclude_none=True))
            journal.export_register(args.root / "case-register.md")
            journal.export_register(args.register_path)
        elif args.command == "quality":
            result = journal.quality()
        elif args.command == "register":
            result = journal.export_register(args.register_path)
        else:
            result = journal.case(args.case_id) if args.case_id else journal.cases()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.resolution_file:
        parser.error("resolution files are forbidden during analysis")
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
            discovery_feeds=args.discovery_feed
            or ["https://www.deraktionaer.de/aktionaer-news.rss"],
        )
        issuers = json.loads(args.product_issuers.read_text()) if args.product_issuers else {}
        engine = Investigator(
            args.root, web=web if args.allow_network else None, product_issuers=issuers
        )
        if args.command == "analyze":
            request = InvestigationRequest(
                teaser_text=args.text_file.read_text() if args.text_file else "",
                teaser_url=args.url,
                original_source_url=args.original_source_url,
                source_retrieved_at=args.source_retrieved_at,
                headline=args.headline,
                publisher=args.publisher,
                author=args.author,
                issue=args.issue,
                evaluation_class=args.evaluation_class,
                previously_used_for_development=False if args.new_blind_case else None,
                publication_at=datetime.fromisoformat(args.publication_at)
                if args.publication_at
                else None,
            )
            packet = json.loads(args.packet.read_text()) if args.packet else None
            result = run_case(
                engine,
                request,
                documents=packet,
                historical_blind=args.historical_blind,
                register_path=args.register_path,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if not args.allow_network:
            parser.error("watch needs explicit --allow-network; never starts implicitly")

        class JournaledEngine:
            def __init__(self, investigator):
                self.investigator = investigator

            def analyze(self, request):
                return run_case(self.investigator, request, register_path=args.register_path)

        monitor = TeaserMonitor(
            args.root,
            web=web,
            engine=JournaledEngine(engine),
            queries=args.query,
            catalog_urls=[] if args.no_catalog else [CATALOG_URL],
            catalog_limit=args.catalog_limit,
        )
        print(json.dumps(monitor.scan_once(), ensure_ascii=False), flush=True)
        if args.once:
            return 0
        for _ in range(args.interval_seconds):
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
