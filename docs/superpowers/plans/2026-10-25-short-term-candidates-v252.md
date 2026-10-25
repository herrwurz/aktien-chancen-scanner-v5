# Scanner V6 V2.5.2 Short-Term Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, read-only short-term stock research dry-run over every eligible instrument in the real V2.5.1 archive.

**Architecture:** Add a focused `scanner.opportunities` package above the existing research index and market-data archive. Pure feature functions consume point-in-time bounded bars; an orchestrator applies explicit gates, catalysts, scoring and non-executable risk scenarios; a CLI emits canonical audit artifacts without network or database writes.

**Tech Stack:** Python 3.12, Pydantic, SQLite read-only mode, pytest, Ruff, Docker.

**Spec:** `docs/superpowers/specs/2026-10-24-short-term-candidates-v252-design.md`

## Global Constraints

- Research horizon is 1–20 sessions; no order, execution claim, probability, or backtest.
- Real pilot is `partial`; dry-run uses `modeled`, `training_eligible=false`, and eight eligible 250-session rows.
- No provider network access, paid booking, production migration, deployment, merge, Immich, or JNJ work.
- Missing calendar, benchmark, quote, catalyst, delisting, or historical availability evidence remains explicit.

## Review Focus

- A bar after `signal_date` must never enter any feature or baseline.
- Adjusted price/volume gaps caused by a split must not become false technical events.
- Missing prior sessions or adjusted fields must fail closed instead of shortening a denominator.
- Similar tickers, funds, and ResearchIndex/archive identity conflicts must not be silently joined.
- Equal scores and repeated runs must produce byte-identical ordered payloads.

---

### Task 1: Read-only archive universe

**Files:** `scanner/market_data/archive.py`, `tests/test_opportunities_v252.py`

**Interfaces:** Produces `MarketDataArchive(path, read_only=True)` and `list_instruments() -> list[dict]` over the existing V2.5.1 schema.

- [x] Write failing tests proving read-only open does not create a file/schema and returns canonical listings without mutation.
- [x] Run focused tests and confirm expected failures.
- [x] Implement SQLite `mode=ro`, schema validation, and deterministic listing enumeration.
- [x] Run focused tests and commit.

### Task 2: Point-in-time feature engine

**Files:** `scanner/opportunities/{__init__,models,features}.py`, `tests/test_opportunities_v252.py`

**Interfaces:** Produces `compute_features(bars, *, signal_date, benchmark_bars=None) -> TechnicalFeatures` from V2.5.1 price dictionaries.

- [x] Write failing tests for 5/10/20 momentum, prior-20 volume ratio, median dollar volume, ATR(14), gap, SMA trend, prior-20 high/breakout and relative strength.
- [x] Prove a future bar does not change the result and incomplete lookbacks/adjusted values fail closed.
- [x] Prove adjusted split data avoids a false raw-price event while raw/reference values remain preserved.
- [x] Implement pure Decimal calculations and strict output model.
- [x] Run focused tests and commit.

### Task 3: Catalysts, gates, score and research risk

**Files:** `scanner/opportunities/{catalysts,short_term}.py`, `tests/test_opportunities_v252.py`

**Interfaces:** Produces `evaluate_candidate(identity, bars, *, as_of, catalysts, benchmark_bars=None, policy=None) -> OpportunityCandidate`.

- [x] Write failing tests for late/unproved news, evidence classes, fund and identity gates, 250-session pilot gate, liquidity, staleness, status and score components.
- [x] Write failing tests proving spread is unavailable and net CRV is null without observed quotes.
- [x] Implement deterministic catalysts, gates, score reasons, technical trigger and ATR risk scenario.
- [x] Run focused tests and commit.

### Task 4: Whole-archive dry-run and reports

**Files:** `scanner/opportunities/{report,cli}.py`, `scanner/research_index/repository.py`, `tests/test_opportunities_v252.py`

**Interfaces:** Produces `run_dry_run(index, archive, *, as_of, signal_date, benchmark_asset_id=None) -> dict` and canonical JSON/CSV/SHA files.

- [x] Write failing end-to-end tests for whole-archive discovery, unavailable rows, stable tie ordering, coverage metrics, zero requests/cost and byte-identical artifacts.
- [x] Implement read-only orchestration and CLI; never accept network or trading flags.
- [x] Run focused tests and commit.

### Task 5: Real pilot procedure, coverage and V2.5.3 handoff

**Files:** `docs/short-term-opportunities-v252.md`, `docs/short-term-opportunities-v252-pilot.md`, `docs/superpowers/specs/2026-10-24-walk-forward-v253-design.md`

- [x] Document PXED/VOGX evidence limits, legal calendar options, incremental Tiingo updates and independently selected universe expansion.
- [x] Provide an isolated, read-only Hetzner command and label output as limited modeled research.
- [ ] Run the authorized real dry-run; record aggregate SHA-bound results without committing licensed raw data.
- [x] Document V2.5.3 blockers without implementing backtesting.
- [ ] Run Ruff, full pytest, Compose, Docker, push a separate PR and wait for GitHub Actions.
