"""Generate public artificial examples; never reads DATABASE_URL or real data.

Run from repo with PYTHONPATH=.:tests/hebeltrader; see backtest documentation
for the generator command and a new output directory.
"""

import argparse
import json
from pathlib import Path

from backtest_sample import AS_OF, RUN_AT, market_inputs, rule_inputs, seed_sample
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scanner.hebeltrader.backtest_cli import write_report
from scanner.hebeltrader.backtest_provider import CsvStockProvider
from scanner.hebeltrader.backtest_report import build_report
from scanner.models import Base


def main():
    parser = argparse.ArgumentParser(description="Synthetic example only; in-memory SQLite")
    parser.add_argument("--output-dir", required=True, type=Path)
    root = parser.parse_args().output_dir
    root.mkdir(parents=True, exist_ok=False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        rules = rule_inputs(doc, rec)
        (root / "synthetic-source.pdf").write_bytes(doc.original_pdf)
    mapping = market_inputs(root)
    for name, value in (("mapping", mapping), ("rules", rules)):
        (root / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    with sessions() as session:
        report = build_report(
            session, CsvStockProvider(root), mapping, rules, as_of=AS_OF, run_at=RUN_AT
        )
    write_report(root / "report.json", report)
    write_report(root / "report.csv", report)
    engine.dispose()


if __name__ == "__main__":
    main()
