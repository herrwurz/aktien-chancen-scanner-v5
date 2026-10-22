# HEBELTRADER Backtesting V1 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or independent bounded agent tasks; checkbox tracking below.

**Goal:** Complete PR #5 against Issue #4 with conservative, auditable offline analysis.
**Architecture:** Retain existing models. Separate pure simulation, offline provider,
read-only orchestration and report serialization. No production writes.
**Tech Stack:** Python 3.12, SQLAlchemy, PostgreSQL, pytest; no new dependencies.
**Spec:** ../specs/2026-10-22-hebel-backtest-design.md

## Global Constraints
No deployment, paid API, trade, scheduler or schema migration. No archive labels.
Unknown is a valid result. Original and modeled return never conflated.

## Review Focus
- A new stop after a target within a bar must not imply an observed event order.
- Missing first session or split must not silently change modeled entry.
- Pending/rejected/revised documents must not become training ground truth.
- A future/incomplete bar must not influence an as-of result.
- Report failures must not overwrite originals or existing reports.

## Tasks

### 1. Simulator
Files: scanner/hebeltrader/backtest.py, tests/test_hebel_backtest.py.
Produces Bar(at, open, high, low, close, end_at=None, volume=None),
Rules(after_target1, close_after_days, close_unit), simulate_stock(..., rules=None).
- [x] Add failing tests for explicit rules, partial exits, gaps, intrabar and expiry.
- [x] Implement finite-value guards, as-of filtering, documented stops and model-only returns.
- [x] Run engine tests and inspect conservative ambiguity cases.

### 2. Provider
Files: scanner/hebeltrader/backtest_provider.py, tests/test_hebel_backtest_provider.py.
Produces HistoricalStockProvider.load(spec, instrument, available_at, as_of),
MarketHistory(bars, source, issues); CsvStockProvider(root).
- [x] Add failing tests for sessions, currencies, actions, paths and historical windows.
- [x] Validate explicit metadata and raw OHLCV; return categorized issues, no network.
- [x] Run provider tests with holiday and delisting fixtures.

### 3. Read-only reports and rules
Files: backtest_cli.py, backtest_report.py, cli.py; tests/hebeltrader/test_backtest_report.py.
- [x] Test 118 pending rows without availability/data, untouched DB and outcome count.
- [x] Add per-document evidence-checked rule sidecar and strict availability gates.
- [x] Export JSON/CSV with sources, hashes, reasons, coverage and no success claims.
- [x] Test private exclusive outputs, malformed input and repeatable read-only runs.

### 4. Documentation and verification
Files: docs/hebeltrader-backtest-v1.md, docs/examples/hebel-backtest/*.
- [x] Document source/coverage/cost decision and explicit local start/rollout plan.
- [x] Generate synthetic example JSON/CSV from actual CLI and test golden outputs.
- [x] Run pytest with disposable PostgreSQL, Ruff, Compose and Docker smoke checks.
- [x] Independent review, resolve findings, push PR #5, await GitHub-CI.
