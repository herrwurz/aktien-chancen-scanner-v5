"""Offline derivative product/quote audit and bid/ask research backtest."""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .cli import write_json
from .derivative_coverage import prioritize_acquisition, write_coverage
from .derivative_model import build_three_mode_report
from .derivative_quotes import (
    DerivativeRules,
    import_quote_file,
    quote_archive_ready,
    read_quote_archive,
    simulate_derivative_quotes,
    verify_product_terms,
)
from .derivative_v20 import build_v20_report, render_v20_markdown
from .eodhd import sha
from .historical_inputs import audit_batch_readiness, load_historical_market_inputs


def _load(path):
    return json.loads(Path(path).read_bytes())


def _add_scenario_arguments(parser, *, require_historical=False):
    parser.add_argument("--underlying", required=True, type=Path)
    parser.add_argument("--prehistory", required=require_historical, type=Path)
    parser.add_argument("--fx", required=require_historical, type=Path)
    parser.add_argument("--input-audit", required=require_historical, type=Path)
    parser.add_argument("--expected-underlying-manifest-sha256")
    parser.add_argument("--expected-current-sessions", type=int)
    parser.add_argument("--expected-prehistory-prices", type=int)
    parser.add_argument("--expected-fx-fixings", type=int)
    parser.add_argument("--expected-dividends", type=int)
    parser.add_argument("--expected-splits", type=int)
    parser.add_argument("--assumptions", required=True, type=Path)
    parser.add_argument("--publication-at", required=True)
    parser.add_argument("--output", required=True, type=Path)


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
    scenario = commands.add_parser("scenario")
    _add_scenario_arguments(scenario)
    scenario_v20 = commands.add_parser("scenario-v20")
    _add_scenario_arguments(scenario_v20, require_historical=True)
    readiness = commands.add_parser("readiness")
    readiness.add_argument("--manifest", required=True, type=Path)
    readiness.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {"scenario", "scenario-v20"}:
            underlying = _load(args.underlying)
            if (
                args.expected_underlying_manifest_sha256 is not None
                and underlying.get("manifest_sha256") != args.expected_underlying_manifest_sha256
            ):
                raise ValueError("underlying manifest mismatch")
            historical_paths = (args.prehistory, args.fx, args.input_audit)
            if any(historical_paths) and not all(historical_paths):
                raise ValueError("prehistory, FX and input audit must be supplied together")
            historical_inputs = (
                load_historical_market_inputs(
                    args.underlying, args.prehistory, args.fx, args.input_audit
                )
                if all(historical_paths)
                else None
            )
            if historical_inputs is not None:
                quality = historical_inputs["quality"]
                expected_quality = {
                    "current_session_count": args.expected_current_sessions,
                    "prehistory_price_count": args.expected_prehistory_prices,
                    "fx_fixing_count": args.expected_fx_fixings,
                    "dividend_event_count": args.expected_dividends,
                    "split_event_count": args.expected_splits,
                }
                for key, expected in expected_quality.items():
                    if expected is not None and quality[key] != expected:
                        raise ValueError(f"historical input coverage mismatch: {key}")
            builder = (
                build_v20_report if args.command == "scenario-v20" else build_three_mode_report
            )
            result = builder(
                underlying["bars"],
                assumptions=_load(args.assumptions),
                publication_at=datetime.fromisoformat(args.publication_at),
                historical_inputs=historical_inputs,
            )
            result["underlying_source"] = {
                key: underlying.get(key) for key in ("provider", "raw_sha256", "manifest_sha256")
            }
            result["input_sha256"] = {
                "underlying_file": sha(args.underlying.read_bytes()),
                "assumptions_file": sha(args.assumptions.read_bytes()),
            }
        elif args.command == "readiness":
            payload = _load(args.manifest)
            result = audit_batch_readiness(payload["recommendations"])
        elif args.command == "prioritize":
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
            if args.command == "scenario-v20":
                markdown_output = args.output.with_suffix(".md")
                markdown_output.parent.mkdir(parents=True, exist_ok=True)
                markdown_output.write_text(render_v20_markdown(result), encoding="utf-8")
        print(json.dumps({"status": result.get("status", "imported")}))
        return 2 if result.get("status") == "blocked" else 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
