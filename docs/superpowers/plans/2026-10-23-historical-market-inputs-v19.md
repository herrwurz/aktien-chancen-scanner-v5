# Historical Market Inputs V1.9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed point-in-time rolling volatility and ECB FX into the existing three-mode HS5RMP report.

**Architecture:** Add one offline input module, adapt the V1.8 model through explicit dated inputs,
and extend the existing derivative CLI. Keep private files external and emit SHA-bound audits.

**Tech Stack:** Python 3.12, Decimal, csv/json, pytest, Ruff, Docker.

**Spec:** `docs/superpowers/specs/2026-10-23-historical-market-inputs-v19-design.md`

## Global Constraints

- No network, paid API, deployment, merge, database write, or private market-data commit.
- No lookahead: volatility and FX used for a session must be available before that session.
- Realized volatility, modeled IV, observed derivative quotes, and stock signals remain distinct.

## Review Focus

- Missing 120-session history must block only scenarios that require it.
- Weekends and ECB holidays must use the latest earlier fixing and disclose its age.
- Duplicate dates, future fixings, provider mismatch, and split events must be visible or blocking.
- Entry comparison must use the first complete post-publication session.
- Batch readiness must never launch a model with unverified product inputs.

### Task 1: Point-in-time market inputs

**Files:** Create `scanner/hebeltrader/historical_inputs.py`; test
`tests/hebeltrader/test_historical_inputs.py`.

- [ ] Write failing tests for annualized sample volatility, strict prior-date FX lookup, missing
  windows, duplicate dates, SHA provenance, and provider mismatch.
- [ ] Implement normalized-file and ECB-CSV readers plus dated series preparation.
- [ ] Run focused tests and commit.

### Task 2: Historical-input BSM scenarios

**Files:** Modify `scanner/hebeltrader/derivative_model.py`; modify its tests.

- [ ] Write failing tests for dated FX, IV multipliers, entry-price comparison, sensitivity fields,
  no lookahead, and missing-window blocking.
- [ ] Pass dated inputs through `_fair` and scenario paths without changing mode boundaries.
- [ ] Run focused and regression tests and commit.

### Task 3: Offline CLI, readiness audit, and documentation

**Files:** Modify `scanner/hebeltrader/derivatives_cli.py`; create V1.9 docs/config example and CLI
tests.

- [ ] Write failing end-to-end tests using synthetic private-file substitutes.
- [ ] Add explicit prehistory, ECB and audit arguments and a readiness-only batch command.
- [ ] Document a direct Docker command for the four existing Hetzner files.
- [ ] Run the offline Docker smoke test and commit.

### Task 4: Release verification

- [ ] Run pytest, Ruff check/format, compose validation and Docker build.
- [ ] Push a new branch, create a PR against `main`, and wait for green GitHub Actions.
- [ ] Do not merge or deploy.
