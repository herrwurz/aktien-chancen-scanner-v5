import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text

from scanner.db import create_db, create_sessions
from scanner.hebeltrader.analysis import FEATURE_FIELDS, export_features, review_document
from scanner.hebeltrader.config import ImportSettings
from scanner.hebeltrader.importer import import_folder
from scanner.hebeltrader.models import Document, HistoricalRecommendation, SourceLocation
from scanner.hebeltrader.quality import preview_database


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Never overwrite an original, another run's report or follow an existing symlink.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    path.chmod(0o600)


def inspect_document(session, sha):
    document = session.get(Document, sha)
    if document is None:
        raise ValueError("Unknown document")
    recs = session.scalars(
        select(HistoricalRecommendation)
        .where(HistoricalRecommendation.document_sha == sha)
        .order_by(HistoricalRecommendation.ordinal)
    )
    locations = session.scalars(select(SourceLocation).where(SourceLocation.document_sha == sha))
    return dict(
        sha256=sha,
        publication_date=document.publication_date,
        extractor_version=document.extractor_version,
        review_status=document.review_status,
        revision_conflict=document.revision_conflict,
        flags=document.flags,
        metadata_evidence=document.metadata_evidence,
        verified_available_at=document.verified_available_at,
        availability_evidence=document.availability_evidence,
        sources=[
            dict(
                relative_path=location.relative_path,
                categories=location.categories,
                category_verification="unverified",
            )
            for location in locations
        ],
        recommendations=[
            dict(
                ordinal=r.ordinal,
                values={k: getattr(r, k) for k in (*FEATURE_FIELDS, "source_commentary")},
                evidence=r.evidence,
                calculated_crv=r.evidence.get("_calculated_crv", []),
                flags=r.flags,
            )
            for r in recs
        ],
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "backtest":
        from scanner.hebeltrader.backtest_cli import main as backtest_main

        return backtest_main(argv[1:])
    parser = argparse.ArgumentParser(
        description="Local historical publication analysis; no trading"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backtest", help="Read-only stock OHLCV analysis (backtest --help)")
    load = commands.add_parser("import")
    load.add_argument("--pdf-dir", type=Path)
    load.add_argument("--report-dir", type=Path)
    load.add_argument("--expected-count", type=int)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--sha", required=True)
    review = commands.add_parser("review")
    review.add_argument("--sha", required=True)
    review.add_argument("--action", required=True, choices=["approve", "reject"])
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", required=True)
    review.add_argument(
        "--available-at", help="Verified source availability, ISO timestamp with timezone"
    )
    review.add_argument(
        "--availability-evidence", help="Archive/source evidence for that timestamp"
    )
    export = commands.add_parser("export")
    export.add_argument("--as-of", required=True)
    export.add_argument("--output", type=Path, required=True)
    quality = commands.add_parser(
        "quality", help="Read-only replay; never update existing extractions"
    )
    quality.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        settings = ImportSettings()
        engine = create_db(settings)
        sessions = create_sessions(engine)
        if args.command == "import":
            expected = (
                args.expected_count
                if args.expected_count is not None
                else settings.hebeltrader_expected_count
            )
            if expected is not None and expected < 1:
                raise ValueError("Expected count must be positive")
            summary = import_folder(
                sessions, args.pdf_dir or settings.hebeltrader_pdf_dir, expected
            )
            report = (
                args.report_dir or settings.hebeltrader_report_dir
            ) / f"import-{summary['id']}.json"
            write_json(report, summary)
            print(json.dumps(summary, ensure_ascii=False, default=str))
            return 2 if summary["failed"] or summary["warnings"] else 0
        if args.command == "inspect":
            with sessions() as session:
                print(
                    json.dumps(inspect_document(session, args.sha), ensure_ascii=False, default=str)
                )
        elif args.command == "review":
            with sessions.begin() as session:
                review_document(
                    session,
                    args.sha,
                    args.action,
                    args.reviewer,
                    args.note,
                    available_at=datetime.fromisoformat(args.available_at)
                    if args.available_at
                    else None,
                    availability_evidence=args.availability_evidence,
                )
            print(json.dumps(dict(sha256=args.sha, action=args.action)))
        elif args.command == "quality":
            with sessions() as session:
                if engine.dialect.name == "postgresql":
                    session.execute(text("SET TRANSACTION READ ONLY"))
                report = preview_database(session)
            write_json(args.output, report)
            print(json.dumps(dict(before=report["before"], after=report["after"]), default=str))
            return 2 if report["after"]["errors"] else 0
        else:
            as_of = datetime.fromisoformat(args.as_of)
            with sessions() as session:
                rows = export_features(session, as_of)
            write_json(args.output, rows)
            print(json.dumps(dict(exported=len(rows))))
        return 0
    except Exception as exc:
        # SQLAlchemy errors may include passwords, original text and bind parameters.
        print(
            json.dumps(dict(status="error", error=type(exc).__name__)),
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()
