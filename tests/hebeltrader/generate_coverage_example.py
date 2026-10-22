"""Synthetic inventory only: ignores DATABASE_URL; all data fabricated in memory."""

import argparse
import hashlib
import json
from pathlib import Path

from backtest_sample import AS_OF, RUN_AT, seed_sample
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scanner.hebeltrader.coverage import build_coverage
from scanner.hebeltrader.coverage_cli import write_reports
from scanner.hebeltrader.models import Document, HistoricalRecommendation
from scanner.models import Base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--count", type=int, default=118)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("count must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        original, rec = seed_sample(session)
        original.verified_available_at = None
        original.availability_evidence = None
        source = {
            column.name: getattr(original, column.name) for column in Document.__table__.columns
        }
        values = {
            column.name: getattr(rec, column.name)
            for column in HistoricalRecommendation.__table__.columns
            if column.name not in {"id", "document_sha"}
        }
        for index in range(1, args.count):
            # A trailing PDF comment distinguishes fabricated sources without altering quoted pages.
            data = source["original_pdf"] + f"\n% SYNTHETIC source {index}\n".encode()
            sha = hashlib.sha256(data).hexdigest()
            session.add(
                Document(**dict(source, sha256=sha, original_pdf=data, byte_size=len(data)))
            )
            session.add(HistoricalRecommendation(document_sha=sha, **values))
    with sessions() as session:
        report = build_coverage(
            session, {}, {}, as_of=AS_OF, run_at=RUN_AT, expected_count=args.count
        )
    write_reports(args.output_dir / "coverage", report)
    summary = {k: v for k, v in report.items() if k not in {"results", "manual_review"}}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    engine.dispose()


if __name__ == "__main__":
    main()
