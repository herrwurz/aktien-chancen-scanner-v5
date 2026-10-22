"""Offline inventory command. Database reads only; explicit private report pair."""

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from scanner.db import create_db, create_sessions
from scanner.hebeltrader.config import ImportSettings
from scanner.hebeltrader.coverage import build_coverage

FIELDS = (
    "recommendation_key",
    "document_sha",
    "ordinal",
    "publication_date",
    "stock_wkn",
    "stock_isin",
    "stages",
    "blockers",
    "rule_candidates",
    "record_json",
    "report_audit",
)


def write_reports(prefix, payload):
    prefix = Path(prefix)
    # Append suffixes; never silently replace a user-supplied filename extension.
    targets = [Path(str(prefix) + ext) for ext in (".json", ".csv")]
    prefix.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    streams = []
    created = []
    try:
        for target in targets:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(target)
            streams.append(os.fdopen(descriptor, "w", encoding="utf-8", newline=""))
        json.dump(payload, streams[0], ensure_ascii=False, indent=2, default=str)
        streams[0].write("\n")
        writer = csv.DictWriter(streams[1], fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        audit = {k: v for k, v in payload.items() if k not in {"results", "manual_review"}}
        for row in payload["results"]:
            record = {k: row.get(k) for k in FIELDS if k in row}
            record.update(
                stock_wkn=row["values"].get("stock_wkn"),
                stock_isin=row["values"].get("stock_isin"),
                record_json=row,
                report_audit=audit,
            )
            writer.writerow(
                {
                    k: json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
                    if isinstance(v, (list, dict))
                    else v
                    for k, v in record.items()
                }
            )
        for stream in streams:
            stream.close()
        return targets
    except BaseException:
        for stream in streams:
            stream.close()
        for target in created:
            target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline HEBELTRADER coverage inventory; read-only"
    )
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--run-at", help="Explicit replay clock for reproducible reports")
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--map", type=Path)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--bars-dir", type=Path)
    parser.add_argument("--expected-count", type=int, default=118)
    parser.add_argument("--analysis-mode", choices=("research", "verified"), default="research")
    args = parser.parse_args(argv)
    engine = None
    try:
        mapping = json.loads(args.map.read_text()) if args.map else {}
        rules = json.loads(args.rules.read_text()) if args.rules else {}
        if not isinstance(mapping, dict) or not isinstance(rules, dict):
            raise ValueError("Mappings and rules must be objects")
        engine = create_db(ImportSettings())
        with create_sessions(engine)() as session:
            if engine.dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION READ ONLY"))
            report = build_coverage(
                session,
                mapping,
                rules,
                as_of=datetime.fromisoformat(args.as_of),
                run_at=datetime.fromisoformat(args.run_at) if args.run_at else datetime.now(UTC),
                bars_dir=args.bars_dir,
                expected_count=args.expected_count,
                analysis_mode=args.analysis_mode,
            )
        paths = write_reports(args.output_prefix, report)
        print(
            json.dumps(
                dict(
                    count=report["count"],
                    summary=report["summary"],
                    warnings=report["warnings"],
                    outputs=[str(p) for p in paths],
                )
            )
        )
        return 2 if report["warnings"] else 0
    except Exception as exc:
        print(json.dumps(dict(status="error", error=type(exc).__name__)), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
