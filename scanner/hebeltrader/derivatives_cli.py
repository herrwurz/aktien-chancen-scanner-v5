"""Offline derivative product/quote audit and bid/ask research backtest."""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .cli import write_json
from .derivative_coverage import prioritize_acquisition, write_coverage
from .derivative_quotes import (
    DerivativeRules,
    import_quote_file,
    quote_archive_ready,
    read_quote_archive,
    simulate_derivative_quotes,
    verify_product_terms,
)


def _load(path):
    return json.loads(Path(path).read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("import-quotes")
    load.add_argument("--input", required=True, type=Path)
    load.add_argument("--metadata", required=True, type=Path)
    load.add_argument("--archive-dir", required=True, type=Path)
    load.add_argument("--output", required=True, type=Path)
    run = commands.add_parser("backtest")
    run.add_argument("--archive-dir", required=True, type=Path)
    run.add_argument("--manifest-sha256", required=True)
    run.add_argument("--product-terms", required=True, type=Path)
    run.add_argument("--rules", required=True, type=Path)
    run.add_argument("--publication-at", required=True)
    run.add_argument("--capital")
    run.add_argument("--unit-size", type=int, default=1)
    run.add_argument("--fee-per-order", default="0")
    run.add_argument("--enforce-quote-size", action="store_true")
    run.add_argument("--output", required=True, type=Path)
    prioritize = commands.add_parser("prioritize")
    prioritize.add_argument("--input", required=True, type=Path)
    prioritize.add_argument("--output-prefix", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prioritize":
            result = prioritize_acquisition(_load(args.input))
            write_coverage(args.output_prefix, result)
        elif args.command == "import-quotes":
            result = import_quote_file(args.input, args.archive_dir, metadata=_load(args.metadata))
        else:
            archive = read_quote_archive(args.archive_dir, args.manifest_sha256)
            terms = verify_product_terms(_load(args.product_terms))
            quote_review = quote_archive_ready(archive["metadata"])
            if not terms["verified"] or not quote_review["approved"]:
                result = {
                    "status": "blocked",
                    "blocker": (
                        "historical_product_terms_unverified"
                        if not terms["verified"]
                        else "quote_hours_gaps_or_usage_rights_unverified"
                    ),
                    "product_terms": terms,
                    "quote_archive_review": quote_review,
                    "return_pct": None,
                    "training_eligible": False,
                }
            else:
                values = _load(args.rules)
                rules = DerivativeRules(
                    target1=Decimal(values["target1"]),
                    target2=Decimal(values["target2"]),
                    stop1=Decimal(values["stop1"]),
                    partial_fraction=Decimal(values["partial_fraction"]),
                    after_target1=values["after_target1"],
                    loss_after_days=values.get("loss_after_days"),
                    loss_unit=values.get("loss_unit"),
                )
                result = simulate_derivative_quotes(
                    archive["quotes"],
                    publication_at=datetime.fromisoformat(args.publication_at),
                    last_trading_at=datetime.fromisoformat(terms["candidate"]["last_trading_at"]),
                    rules=rules,
                    capital=Decimal(args.capital) if args.capital is not None else None,
                    unit_size=args.unit_size,
                    fee_per_order=Decimal(args.fee_per_order),
                    enforce_quote_size=args.enforce_quote_size,
                )
                result["quote_manifest_sha256"] = args.manifest_sha256
                result["product_source_sha256"] = terms["candidate"]["source_sha256"]
        if args.command != "prioritize":
            write_json(args.output, result)
        print(json.dumps({"status": result.get("status", "imported")}))
        return 2 if result.get("status") == "blocked" else 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
