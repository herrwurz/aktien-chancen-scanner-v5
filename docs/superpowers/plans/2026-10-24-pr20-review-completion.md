# PR #20 Review Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close review #5637329591 with evidence-gated retrieval, resilient news collection, point-in-time revisions, a ten-case benchmark, and a V2.5 design.

**Architecture:** Keep the existing SQLite/FTS5 index and shared research facade. Add explicit instrument classification and separate identity/evidence retrieval channels, isolate providers behind a collector, and represent revisions in the immutable index so `as_of` selects only the then-current record.

**Tech Stack:** Python 3.12, Pydantic, SQLite FTS5, httpx, pytest, Ruff, Docker.

**Spec:** GitHub review `5637329591` and `docs/superpowers/specs/2026-10-24-stock-search-index-v24-design.md`

## Global Constraints

- No deployment, merge, productive database mutation, paid booking, automated orders, or Immich changes.
- Real and synthetic evidence and benchmark results remain explicitly separated.
- Network access stays opt-in and bounded.

## Review Focus

- Generic identity words must not outrank event evidence.
- Funds must not masquerade as operating companies.
- A failed provider must not discard successful provider results.
- Corrections must become visible only at their own availability time.
- Missing timestamps and coverage must yield unavailable or unresolved, never fabricated certainty.

---

### Task 1: Evidence-gated candidate retrieval

**Files:** `scanner/research.py`, `scanner/research_index/{builder,models,repository}.py`, `tests/test_research_index_v24.py`

- [x] Add failing tests for fund downranking, separate evidence/identity text channels, weak-only unresolved results, and transparent coverage.
- [x] Add instrument classification provenance and channel-specific FTS rows.
- [x] Implement deterministic weighted ranking and a minimum-evidence gate.
- [x] Run focused tests and commit.

### Task 2: Resilient news collection

**Files:** `scanner/news.py`, `scanner/news_collector.py`, `scanner/news_providers/{gdelt,issuer_feed}.py`, `tests/test_news_v24.py`

- [x] Add failing tests for bounded 503 retry, exhausted retry status, partial multi-provider results, active/configured counts, age, and cache integrity.
- [x] Implement bounded retry and a failure-isolating collector without fallback data.
- [x] Run focused tests and commit.

### Task 3: Point-in-time revisions

**Files:** `scanner/news.py`, `scanner/research.py`, `scanner/research_index/{builder,repository}.py`, `tests/test_research_index_v24.py`

- [x] Add failing tests for delayed news, news correction, fact revision, future identity, and missing timestamps.
- [x] Store revision links and suppress superseded records only after the revision becomes available.
- [x] Run focused tests and commit.

### Task 4: Independent benchmark and report

**Files:** `scanner/research_benchmark.py`, `scanner/research_evaluation.py`, `tests/fixtures/research-v24/benchmark.json`, `tests/test_research_v24_e2e.py`, `docs/research-v24*.{md,json}`

- [x] Add a predeclared ten-case cross-sector corpus with solutions separate from teasers and real/synthetic labels.
- [x] Measure Recall@10/50, Top-1/3, abstention, false positives, market/sector coverage, latency, requests, and costs.
- [x] Re-run the archived public-data report and document that the Apple-only result is not an accuracy benchmark.
- [x] Run focused tests and commit.

### Task 5: V2.5 specification and release verification

**Files:** `docs/superpowers/specs/2026-10-24-short-term-stock-scanner-v25-design.md`, `docs/research-v24-source-audit.md`

- [x] Specify providers within 0–20 EUR/month, catalyst/price/volume/liquidity inputs, risk/CRV, costs, and walk-forward validation.
- [x] Document source rights, costs, historical availability, and blockers.
- [ ] Run Ruff, full pytest, Docker build, force-push rebased branch, retarget PR to main, update description, and wait for CI.
