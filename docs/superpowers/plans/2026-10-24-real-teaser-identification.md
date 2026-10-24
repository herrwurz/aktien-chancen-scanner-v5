# V2.3 Real Teaser Identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect archived and explicitly live public-company research to the existing detective with point-in-time facts and auditable coverage.

**Architecture:** A shared factory constructs fixture, cached, or live research sources. Immutable SEC raw caches feed a signed normalized snapshot; deterministic XBRL extraction produces separately verified facts. A GLEIF adapter supplies international legal-entity evidence without pretending to supply news.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, httpx, pytest, existing SHA cache helpers.

**Spec:** `docs/superpowers/specs/2026-10-24-real-teaser-identification-design.md`

## Global Constraints

- Additional data/API budget is 0–20 EUR/month; no paid activation.
- No deployment, merge, production database change, trade, or Immich interaction.
- API startup performs no network access.
- Fixture data is always visibly marked as fixture data.
- Unknown facts and historical identity availability are never inferred.

## Review Focus

- Corrupt or substituted raw cache data must fail closed.
- Missing/late timestamps must exclude evidence from historical ranking.
- A filing form alone must never imply positive performance.
- Live mode must stop at the configured request/candidate limits.
- Candidate selection must be independent of the expected blind-test answer.

---

### Task 1: Common facts and immutable research snapshot

**Files:** `scanner/research.py`, `scanner/research_snapshot.py`, `tests/test_research_v23.py`

- [ ] Write failing tests for fact provenance, unknown comparisons, snapshot SHA validation, and late evidence.
- [ ] Implement `CompanyFact` and canonical snapshot read/write/validation.
- [ ] Run the focused tests and commit.

### Task 2: SEC facts without semantic overclaiming

**Files:** `scanner/research_providers/sec_edgar.py`, `scanner/research_facts.py`, `tests/test_research_v23.py`

- [ ] Write failing tests showing 10-Q is only a document and comparable XBRL periods alone yield increase/decrease facts.
- [ ] Add cached `companyfacts` retrieval and deterministic limited extraction.
- [ ] Run SEC/V2.2/V2.3 tests and commit.

### Task 3: Configured source modes and common CLI/API

**Files:** `scanner/config.py`, `scanner/hebeltrader/detective/factory.py`, `scanner/hebeltrader/detective/cli.py`, `scanner/main.py`, `tests/test_research_v23.py`, `tests/test_api.py`

- [ ] Write failing tests for all modes, startup network silence, identical CLI/API structure, and explicit failures.
- [ ] Implement lazy factory and snapshot-backed candidate source with coverage and age.
- [ ] Run focused API/CLI tests and commit.

### Task 4: Ranking with facts, contradictions and unknown hints

**Files:** `scanner/hebeltrader/detective/clues.py`, `scanner/hebeltrader/detective/service.py`, `tests/test_research_v23.py`

- [ ] Write blind, late-news, unresolved, contradiction and fixed-universe tests.
- [ ] Extend ranking while preserving uncalibrated evidence-strength labels and Top 3 output.
- [ ] Run detective regression tests and commit.

### Task 5: International identity source and strategy contracts

**Files:** `scanner/research_providers/gleif.py`, `scanner/strategy_contracts.py`, `tests/test_research_v23.py`

- [ ] Write failing cache, provenance, temporal and provider-failure tests.
- [ ] Implement bounded GLEIF adapter and explicit short-/medium-term availability schemas.
- [ ] Run focused tests and commit.

### Task 6: Real E2E audit, docs and PR

**Files:** `docs/research-v23.md`, `docs/research-v23-e2e.json`, `README.md`

- [ ] Run a bounded real SEC/GLEIF archive build from a teaser-independent universe selection.
- [ ] Record whether the blind teaser resolves, with real/fixture status and remaining gaps.
- [ ] Run Ruff, pytest, Compose validation, Docker/CI; fix regressions.
- [ ] Push the feature branch and create the requested PR without merging.
