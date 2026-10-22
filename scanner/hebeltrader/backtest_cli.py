"""Read-only offline backtest. No market download and no database writes."""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select, text
from scanner.db import create_db, create_sessions
from scanner.hebeltrader.config import ImportSettings
from scanner.hebeltrader.models import Document, HistoricalRecommendation, SourceLocation
from scanner.hebeltrader.backtest import Bar, simulate_stock, VERSION

def read_bars(path):
    bars = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            bars.append(Bar(datetime.fromisoformat(row["timestamp"]), *(
                Decimal(row[k]) for k in ("open","high","low","close")
            )))
    return bars

def main(argv=None):
    p = argparse.ArgumentParser(description="Offline, read-only historical stock OHLC backtest")
    p.add_argument("--bars-dir", required=True, type=Path, help="Directory of explicitly mapped OHLC CSV files")
    p.add_argument("--map", required=True, type=Path, help="JSON mapping of stock WKN to CSV filename, venue and currency")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--as-of", required=True, help="UTC-aware ISO timestamp ending the evaluation")
    args = p.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of)
    if as_of.tzinfo is None:
        p.error("--as-of needs timezone")
    mapping = json.loads(args.map.read_text(encoding="utf-8"))
    # A deliberate WKN-to-file mapping is mandatory; do not infer tickers from names.
    settings = ImportSettings()
    engine = create_db(settings)
    results = []
    try:
        sessions = create_sessions(engine)
        with sessions() as session:
            if engine.dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION READ ONLY"))
            rows = session.execute(select(HistoricalRecommendation, Document).join(
                Document, HistoricalRecommendation.document_sha == Document.sha256
            ).order_by(Document.publication_date, HistoricalRecommendation.id)).all()
            for rec, doc in rows:
                base = dict(recommendation_id=rec.id, document_sha=doc.sha256,
                            publication_date=str(doc.publication_date), derivative_wkn=rec.derivative_wkn,
                            stock_wkn=rec.stock_wkn, method_version=VERSION,
                            derivative_status="derivative_unverified", result=None, source=None)
                # Conservative: no intraday proof of release time; only next-day onwards.
                if doc.publication_date is None:
                    base["result"] = dict(status="unknown", reason="missing_publication_date")
                elif doc.publication_date > as_of.date():
                    base["result"] = dict(status="unknown", reason="future_publication")
                else:
                    key = rec.stock_wkn
                    spec = mapping.get(key) if key else None
                    if not spec or not all(spec.get(k) for k in ("file", "venue", "currency", "adjustment")):
                        base["result"] = dict(status="unknown", reason="unmapped_stock_instrument")
                    else:
                        filename = spec["file"]
                        path = (args.bars_dir / filename).resolve()
                        if not path.is_relative_to(args.bars_dir.resolve()) or not path.is_file():
                            base["result"] = dict(status="unknown", reason="ohlc_source_missing")
                        else:
                            raw = path.read_bytes()
                            bars = read_bars(path)
                            from datetime import time, timedelta
                            from zoneinfo import ZoneInfo
                            available = doc.verified_available_at or datetime.combine(
                                doc.publication_date + timedelta(days=1), time.min,
                                ZoneInfo("Europe/Berlin")
                            )
                            base["result"] = simulate_stock(
                                available_at=available, bars=bars, target1=rec.stock_target1,
                                target2=rec.stock_target2, stop1=rec.stock_stop1,
                                stop2=rec.stock_stop2, horizon=as_of
                            )
                            base["source"] = dict(file=filename, sha256=hashlib.sha256(raw).hexdigest(),
                                                  venue=spec["venue"], currency=spec["currency"],
                                                  adjustment=spec["adjustment"],
                                                  note="User-provided OHLC; provenance not independently verified")
                results.append(base)
    finally:
        engine.dispose()
    counts = {}
    for r in results:
        status = r["result"]["status"]
        counts[status] = counts.get(status, 0)+1
    payload = dict(method_version=VERSION, as_of=as_of.isoformat(), count=len(results),
                   counts=counts, warning="Research only; OHLC is not derivative bid/ask or executed trades",
                   results=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, default=str)
    print(json.dumps(dict(count=len(results), counts=counts, output=str(args.output))))
if __name__ == "__main__":
    main()
