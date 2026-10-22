"""Read-only offline analysis; no network, database writes or outcome persistence."""

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from scanner.db import create_db, create_sessions
from scanner.hebeltrader.backtest_provider import CsvStockProvider
from scanner.hebeltrader.backtest_report import build_report
from scanner.hebeltrader.config import ImportSettings

CSV_FIELDS = (
    "recommendation_id",
    "document_sha",
    "ordinal",
    "publication_date",
    "available_at",
    "review_status",
    "source_verified",
    "training_eligible",
    "method_version",
    "status",
    "reason",
    "modeled_return_pct",
    "realized_return_pct",
    "derivative_status",
    "instrument",
    "observation_window",
    "source",
    "rules",
    "data_issues",
    "events",
    "audit",
)


def write_report(path, payload):
    path = Path(path)
    if path.suffix not in {".json", ".csv"}:
        raise ValueError("Output must use .json or .csv")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
        if path.suffix == ".json":
            json.dump(payload, stream, indent=2, default=str, ensure_ascii=False)
            stream.write("\n")
        else:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            audit = {k: v for k, v in payload.items() if k != "results"}
            for row in payload["results"]:
                record = {k: row.get(k) for k in CSV_FIELDS if k in row}
                record.update(
                    status=row["result"]["status"],
                    reason=row["result"].get("reason"),
                    modeled_return_pct=row["result"].get("modeled_return_pct"),
                    realized_return_pct=None,
                    derivative_status=row["derivative"]["status"],
                    events=row["result"]["events"],
                    audit=dict(
                        audit,
                        input_sha256=row["input_sha256"],
                        result=row["result"],
                        model_assumptions=row["model_assumptions"],
                        derivative=row["derivative"],
                        availability_evidence=row["availability_evidence"],
                        published_stock_quote=row["published_stock_quote"],
                    ),
                )
                writer.writerow(
                    {
                        k: json.dumps(v, sort_keys=True, default=str, ensure_ascii=False)
                        if isinstance(v, (dict, list))
                        else v
                        for k, v in record.items()
                    }
                )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only historical stock OHLCV analysis")
    parser.add_argument("--bars-dir", required=True, type=Path)
    parser.add_argument(
        "--map", required=True, type=Path, help="Explicit instrument-to-source JSON"
    )
    parser.add_argument("--rules", type=Path, help="Document-SHA:ordinal rule interpretations JSON")
    parser.add_argument("--output", required=True, type=Path, help="New .json or .csv report")
    parser.add_argument("--as-of", required=True, help="Timezone-aware observation cutoff")
    args = parser.parse_args(argv)
    engine = None
    try:
        as_of = datetime.fromisoformat(args.as_of)
        mapping = json.loads(args.map.read_text(encoding="utf-8"))
        rules = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else {}
        if not isinstance(mapping, dict) or not isinstance(rules, dict):
            raise ValueError("Mapping and rules must be objects")
        if args.output.suffix not in {".json", ".csv"}:
            raise ValueError("Output must use .json or .csv")
        engine = create_db(ImportSettings())
        with create_sessions(engine)() as session:
            if engine.dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION READ ONLY"))
            payload = build_report(
                session,
                CsvStockProvider(args.bars_dir),
                mapping,
                rules,
                as_of=as_of,
                run_at=datetime.now(UTC),
            )
        write_report(args.output, payload)
        print(
            json.dumps(
                dict(
                    count=payload["count"],
                    counts=payload["counts"],
                    coverage=payload["coverage"],
                    output=str(args.output),
                )
            )
        )
        return 0
    except Exception as exc:
        # Do not print SQL statements, credentials, source data or filesystem contents.
        print(json.dumps(dict(status="error", error=type(exc).__name__)), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
