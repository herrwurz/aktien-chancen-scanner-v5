# HS5RMP Backtest V1.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable offline path from authorized HS5RMP bid/ask exports to a realistic derivative backtest, while blocking returns when product terms or quote coverage are insufficient.

**Architecture:** Extend the existing immutable quote archive instead of adding a provider download. Separate normalization, coverage qualification, execution simulation, and the 118-product acquisition forecast. Treat the Hetzner Tiingo archive as independent underlying evidence only.

**Tech Stack:** Python 3.12, pytest, existing SHA-256 archive utilities and CLI.

**Spec:** User-provided Scanner V6 V1.8 brief dated 2026-10-23.

## Global Constraints

- No paid booking, undocumented endpoint, deployment, merge, database write, or PDF mutation.
- Only observed bid/ask quotes may produce a derivative return.
- Missing product terms and quote coverage remain explicit blockers.
- Existing V1.7 behavior and tests remain compatible.

## Review Focus

- Sparse or one-sided quotes must never become executable observations.
- A quote after a long outage must not silently satisfy a stop or target at the trigger price.
- Expiry settlement requires separate official evidence and cannot be inferred from the last quote.
- Fees and whole-unit sizing must affect cash results without inventing broker costs.
- Indications and trades must remain distinct from executable bid/ask quotes.

### Task 1: Quote normalization and immutable archive V2

**Files:** Modify `scanner/hebeltrader/derivative_quotes.py`; modify `tests/hebeltrader/test_derivative_quotes.py`.

- [ ] Add failing tests for authorized CSV input, quote status/size preservation, rejected one-sided rows, and immutable replay.
- [ ] Run the focused tests and confirm the new cases fail for missing behavior.
- [ ] Implement deterministic CSV/JSON normalization and archive format V2 while retaining V1 reading.
- [ ] Run focused and existing derivative tests.

### Task 2: Coverage qualification and realistic execution

**Files:** Modify `scanner/hebeltrader/derivative_quotes.py`; modify `tests/hebeltrader/test_derivative_quotes.py`.

- [ ] Add failing tests for availability windows, gaps, spread statistics, lot sizing, fees, censored expiry, and evidenced cash settlement.
- [ ] Confirm expected failures.
- [ ] Implement `audit_quote_coverage` and extend `simulate_derivative_quotes` with explicit execution assumptions and blockers.
- [ ] Run focused tests and preserve V1.7 results.

### Task 3: Read-only pilot and 118-product prioritization

**Files:** Create `scanner/hebeltrader/derivative_coverage.py`; modify `scanner/hebeltrader/derivatives_cli.py`; create `tests/hebeltrader/test_derivative_coverage.py`.

- [ ] Add failing tests for HS5RMP coverage output, no-return gating, Tiingo separation, deterministic JSON/CSV, and four acquisition priority classes.
- [ ] Confirm expected failures.
- [ ] Implement read-only report and CLI commands over supplied local archives.
- [ ] Run focused tests.

### Task 4: Evidence and operator documentation

**Files:** Create `docs/hebeltrader-hs5rmp-backtest-v18.md`; update `README.md`; add reviewed source manifest fixture.

- [ ] Document official HSBC, Börse Stuttgart and Deutsche Börse findings, known unknowns, licensing/contact path, Hetzner commands, and the absence of an actual HS5RMP result.
- [ ] Document Tiingo as plausibility evidence only and the acquisition forecast workflow for all 118 recommendations.
- [ ] Validate all commands offline.

### Task 5: Verification and pull request

- [ ] Run Ruff, complete pytest, PostgreSQL-marked tests where configured, Docker build and Compose validation.
- [ ] Commit, push the feature branch, verify GitHub Actions, and open a PR against `main` without merging.
