"""Read-only JNJ pilot. Network collection is a separate, explicitly authorized command."""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from scanner.db import create_db, create_sessions

from .config import ImportSettings
from .openfigi_archive import audit_archive
from .pilot import CONTINUATION, EXPIRY, JNJ_SHA, build_pilot_report
from .pilot_artifacts import verify_report, write_report


def _load(path, default):
    return json.loads(Path(path).read_bytes()) if path else default


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--run-at", required=True)
    run.add_argument("--end-date", choices=[str(EXPIRY), str(CONTINUATION)], default=str(EXPIRY))
    run.add_argument("--analysis-mode", choices=["research", "verified"], default="research")
    run.add_argument("--output-prefix", type=Path, required=True)
    for name in (
        "map",
        "rules",
        "historical-sources",
        "data-root",
        "eodhd-cache",
        "calendar-review",
        "projection-review",
        "action-review",
        "openfigi",
        "openfigi-cache",
        "linked-identities",
    ):
        run.add_argument("--" + name, type=Path)
    run.add_argument("--bundles", nargs="*", type=Path, default=[])
    run.add_argument("--synthetic", action="store_true")
    run.add_argument(
        "--document-sha",
        default=JNJ_SHA,
        help="Override allowed only with explicitly synthetic test inputs",
    )
    verify = commands.add_parser("verify")
    verify.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command == "verify":
            verify_report(args.output_prefix)
            print(json.dumps(dict(status="integrity_verified")))
            return 0
        if bool(args.openfigi) != bool(args.openfigi_cache) or (
            args.linked_identities and not args.openfigi
        ):
            raise ValueError("OpenFIGI export/raw paths must be paired")
        run_at = datetime.fromisoformat(args.run_at)
        archive = (
            audit_archive(args.openfigi, args.openfigi_cache, args.linked_identities, run_at=run_at)
            if args.openfigi
            else None
        )
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
            report = build_pilot_report(
                session,
                run_at=run_at,
                end_date=date.fromisoformat(args.end_date),
                analysis_mode=args.analysis_mode,
                document_sha=args.document_sha,
                synthetic=args.synthetic,
                records=records,
                mapping=_load(args.map, {}),
                rules=_load(args.rules, {}),
                bundles=[_load(p, {}) for p in args.bundles],
                market_root=args.data_root,
                raw_cache=args.eodhd_cache,
                calendar_review=_load(args.calendar_review, None),
                projection_review=_load(args.projection_review, None),
                action_review=_load(args.action_review, None),
                cache_dir=args.openfigi_cache,
                archive_audit=archive,
            )
            write_report(args.output_prefix, report)
        print(
            json.dumps(
                dict(
                    classification=report["quality"]["classification"],
                    blockers=report["quality"]["blockers"],
                    report_sha256=report["report_sha256"],
                ),
                sort_keys=True,
            )
        )
        return 2 if report["quality"]["blockers"] else 0
    except Exception as exc:
        print(json.dumps(dict(status="error", error=type(exc).__name__)), file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()
