# Tiingo Live Pilot Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close PR #21's remaining operational gaps with a safe one-command Hetzner pilot that uses the existing SEC archive and a renewed Tiingo secret without touching production services.

**Architecture:** Keep the existing Python market-data pipeline unchanged except for input provenance checks required by review #5639603503. Add a small shell entrypoint that mounts the existing research archive read-only, writes into an isolated directory, prompts for the token at runtime, and invokes the existing CLI with bounded free-tier settings.

**Tech Stack:** Bash, Python 3.12, Docker, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-10-24-short-term-stock-scanner-v25-design.md`

## Global Constraints

- Never use or persist a token shared through chat; accept only a renewed runtime secret.
- No paid API, merge, deployment, productive PostgreSQL access, Compose project, or Immich access.
- At most ten equities and thirty bounded HTTP attempts; declared cost remains EUR 0.
- A real run without an independent exchange calendar remains `partial`, never `accepted`.

## Review Focus

- A missing or ambiguous SEC universe manifest must stop before prompting for the secret.
- The SEC reports mount must be read-only and the output directory must be independent.
- `as_of` must be aware and not precede the SEC archive retrieval timestamp.
- The secret must not appear in arguments, files, reports, or shell tracing.
- Failed or partial provider responses must still produce auditable JSON/CSV/SHA artifacts.

---

### Task 1: Provenance gate

**Files:**
- Modify: `scanner/market_data/pilot.py`
- Modify: `scanner/market_data/cli.py`
- Test: `tests/test_market_data_pilot_v251.py`

**Interfaces:**
- Produces: `validate_sec_index_audit(path, index, as_of) -> dict`
- Consumes: existing SEC index audit and `ResearchIndex.manifest.payload_sha256`

- [x] Write failing tests for an `as_of` before archive retrieval, an index hash mismatch, and a valid audit.
- [x] Run focused tests and confirm the expected failures.
- [x] Implement and expose the provenance gate through `pilot --sec-index-audit`.
- [x] Run focused tests and commit with Task 2.

### Task 2: Safe one-command server runner

**Files:**
- Create: `scripts/run-tiingo-pilot.sh`
- Modify: `tests/test_market_data_pilot_v251.py`
- Modify: `docs/market-data-v251.md`

**Interfaces:**
- Consumes: existing `/opt/aktien-chancen-scanner-v5/reports` archive and renewed `TIINGO_API_TOKEN` entered interactively.
- Produces: isolated `coverage.json`, `coverage.csv`, `coverage.sha256`, SEC audit/index, raw snapshots, and SQLite archive.

- [x] Write a shell-level test for the runner's safe runtime configuration surface.
- [x] Run it and confirm failure because the runner is absent.
- [x] Implement the minimal runner with exact manifest discovery, archive timestamp validation through Task 1, secret prompt/trap, and SHA verification.
- [x] Document one pasteable setup/run command and status interpretation.
- [x] Run focused tests and commit.

### Task 3: Release verification

**Files:**
- Modify: PR #21 description/review response only after local verification.

- [x] Run Ruff and full pytest against isolated PostgreSQL.
- [x] Validate both Compose profiles and build the Docker image.
- [x] Push the same branch and wait for all GitHub Actions checks.
- [x] Report the real pilot result only after the authorized server run produced SHA-verified artifacts.
