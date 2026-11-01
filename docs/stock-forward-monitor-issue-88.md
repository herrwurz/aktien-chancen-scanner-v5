# Stock Forward Monitor — isolated foundation (Issue #88)

This increment intentionally does **not** modify `scanner/hebeltrader/**`, HEBELTRADER tests, routes, database, or Cursor development. It also does not change the existing worker, Compose services, or deployment.

## Implemented
- Typed UTC-aware evidence receipts with publication, first-seen and retrieval timestamps, source URL/type and content SHA-256.
- Point-in-time cutoff checks; missing/future evidence fails closed.
- Decision categories: detected, research, paper-entry-eligible, rejected.
- EOD/delayed/unavailable quotes cannot be labeled executable; long paper scenarios require timestamp, entry, stop and target.
- Append-only SHA-256-linked JSONL run records with duplicate-run detection and chain verification.
- Isolated unit tests for cutoff, duplicates, quote restrictions and tampering.

## Not implemented / not claimed
No SEC/EQS/RNS live adapter, realtime quotes, scheduler, alert, execution, persistent database, complete market coverage, fees/spread computation or weekly performance metrics. Hash chaining is tamper-evident against accidental modification, **not** cryptographic proof against a party able to rewrite the entire journal. Storage is local to the caller; production persistence and locking must be designed before multi-process use.

## Next acceptance gate
Read-only provider audit; implement authorized SEC primary-source adapter and original-time receipt capture; validate independent exchange calendar and quote provenance; expand negative tests and integration coverage. Do not enable alerts or deployment until these gates pass. Run `pytest -q tests/test_stock_forward_journal.py` and the existing full CI suite.

Historical Genmab, PodcastOne and Ultralife cases may be used as regression fixtures only when original dated evidence is supplied, not as evidence of a working live feed.
