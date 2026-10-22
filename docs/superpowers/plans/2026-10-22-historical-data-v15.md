# Historical Data V1.5 Implementation Plan

> Execution: native, in the existing isolated feature branch. User's explicit V1.5 implementation/PR instruction authorizes execution; no provider purchases are authorized.

**Goal:** Audit 96 WKN and 118 recommendations without inventing historical mappings, then connect explicitly authorized EODHD snapshots to the existing offline backtest interfaces.

**Architecture:** Keep V1.3/V1.4 parsers, modes and databases unchanged. Add a separate source audit, a gated immutable EODHD collector, a calendar-bound offline adapter and a read-only coverage CLI that reuses `build_coverage`.

**Constraints:** PostgreSQL READ ONLY; SQLite query_only/mode=ro. No production deployment/migration, paid requests, trades or original data modifications. External budget ceiling EUR100/month is not approval to spend. No derivative bid/ask substitution. All candidates unverified until human review with dated evidence.

## Tasks
- [ ] `historical_identity.py`: analyze original OpenFIGI records/cache, preserve venue candidates and security types; detect stock/derivative collisions; source-backed reviewer gate for time intervals, changes and delistings. Tests cover future evidence, overlapping listings, missing cache and changed identifiers.
- [ ] `eodhd.py`: fixed-host optional collector, environment-only key, explicit usage approval, bounded retries and request budget, cache-only mode, content-addressed raw snapshots and manifest integrity. Tests cover tokens, rate limits, tampering, missing approval and caching.
- [ ] `eodhd_adapter.py`: normalize raw OHLC (not adjusted_close), keep split-adjusted volume labeled, consume explicit historical sessions, retain splits/dividends and delisting blockers; export immutable V1.3-compatible local snapshots. Tests cover DST, half-days, missing sessions, corporate actions and lookahead.
- [ ] `pipeline_cli.py`: offline identity/coverage reports for 118, source audit and existing coverage stages, exclusive JSON/CSV output. Tests cover reproducibility, read-only access, stock/derivative separation and no fabricated external results.
- [ ] Run all 118 locally, document actual/source-reported coverage separately, source/pricing references and exact commands. Run Ruff, pytest and full Docker/PostgreSQL CI; open new PR against main.

## Review focus
- Current OpenFIGI listings never establish historical ticker/MIC continuity.
- Missing historical calendars may not be reconstructed from returned price dates or current trading hours.
- Splits/dividends/delistings require explicit reconciliation rather than guessed fills.
- Credentials and authenticated URLs must not enter files, errors or reports.
- Manual review alone without field-bound source evidence cannot manufacture verified identities.
