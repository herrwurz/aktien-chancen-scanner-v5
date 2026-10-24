# V2.4 Research Index and News Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real, provenance-bound news intake and a point-in-time SQLite/FTS5 candidate index shared by the detective and future opportunity strategies.

**Architecture:** Existing SEC/GLEIF normalized records feed a versioned SQLite artifact. New `NewsSource` providers add bounded GDELT metadata and explicitly allowlisted RSS/Atom issuer feeds. Stage A retrieves up to 50 candidates across the complete indexed universe; the existing detective performs Stage B evidence ranking and returns at most three.

**Tech Stack:** Python 3.12 standard library, Pydantic, HTTPX, SQLite FTS5, pytest.

**Spec:** `docs/superpowers/specs/2026-10-24-stock-search-index-v24-design.md`

## Global Constraints

- Additional provider/AI cost stays within 0–20 EUR/month; no purchase without approval.
- No production database migration, deployment, trading, JNJ work, or changes to other Docker projects.
- Network is disabled by default; raw records are immutable and SHA-256 verified.
- Provider terms and article copyright are respected; no paywall, CAPTCHA or access-control bypass.
- Primary, secondary and community evidence remain separate; probabilities are not claimed.

## Review Focus

- Similar company names must not cause an identifier assignment without a matching proven identifier.
- Syndicated copies must retain all URLs but count as one underlying evidence cluster.
- Corrected or late records must remain invisible before `source_available_at`.
- Empty, stale, malformed or unavailable provider responses must yield explicit coverage errors.
- Broad teaser queries must abstain when Stage A cannot narrow the universe meaningfully.

---

### Task 1: Normalized news contract and clustering

**Files:** Create `scanner/news.py`, `scanner/news_cluster.py`; test `tests/test_news_v24.py`.

**Interfaces:** Produce `NewsItem`, `NewsBatch`, `NewsSource.fetch(query, *, start, end, limit)`, and `cluster_news(items)`.

- [ ] Write failing tests for required fields, evidence classes, community non-confirmation, and independent-origin clustering.
- [ ] Run focused tests and observe missing-module failures.
- [ ] Implement the minimal models/protocol and deterministic clusterer.
- [ ] Run focused tests and commit the green task.

### Task 2: Immutable provider cache and real GDELT adapter

**Files:** Create `scanner/news_providers/cache.py`, `scanner/news_providers/gdelt.py`; test `tests/test_news_v24.py`.

**Interfaces:** Produce `GdeltNewsSource.fetch(...) -> NewsBatch`; consume immutable cache helpers and explicit `allow_network`, request, size and timeout limits.

- [ ] Write failing tests for normalization, PIT exclusion, cache SHA validation, request limits, timeouts and provider failure.
- [ ] Verify expected failures, then implement metadata-only DOC 2.0 ingestion.
- [ ] Run tests with mocked HTTP, then execute one bounded real request and archive only a compact audit report.
- [ ] Commit the green task.

### Task 3: Allowlisted issuer RSS/Atom adapter

**Files:** Create `scanner/news_providers/issuer_feed.py`; test `tests/test_news_v24.py`.

**Interfaces:** Produce `IssuerFeedConfig` and `IssuerFeedNewsSource.fetch(...) -> NewsBatch` using standard-library XML parsing.

- [ ] Write failing tests for RSS and Atom, explicit issuer identifiers, `PRIMARY` classification, missing license refusal, XXE/oversize rejection and similar-name safety.
- [ ] Verify failures and implement only allowlisted configured feeds.
- [ ] Run focused tests and commit the green task.

### Task 4: Reproducible SQLite/FTS5 research index

**Files:** Create `scanner/research_index/{models.py,builder.py,repository.py,retrieval.py}`; test `tests/test_research_index_v24.py`.

**Interfaces:** Produce `build_index(path, assets, events, facts, news, manifest)`, `ResearchIndex`, `candidate_search(query, as_of, limit<=50)` and coverage methods.

- [ ] Write failing tests for deterministic builds, integrity manifests, full-universe counts, PIT revisions, FTS/structured retrieval and out-of-index abstention.
- [ ] Verify failures and implement a temporary-file build followed by integrity check and atomic replace.
- [ ] Implement Stage-A channel fusion with per-channel reserve and `insufficiently_constrained`.
- [ ] Run focused tests and commit the green task.

### Task 5: Detective and shared strategy integration

**Files:** Create `scanner/hebeltrader/detective/index_source.py`; modify `scanner/research_service.py`, detective factory/CLI; test `tests/test_research_index_v24.py` and `tests/test_research_v24_e2e.py`.

**Interfaces:** Implement `research.universe`, `research.candidates`, `research.events`, `research.fundamentals`, `research.prices`, `research.coverage`; adapt Stage-A rows to existing Stage-B ranking.

- [ ] Write failing tests proving all retrieved candidates are verified before Top-3, unknown clues remain neutral, and both future opportunity strategy views have availability rather than signals.
- [ ] Verify failures and connect existing models/services without duplicating ranking logic.
- [ ] Run backward-compatibility tests and commit the green task.

### Task 6: Evaluation, real audit and documentation

**Files:** Create `scanner/research_evaluation.py`, `docs/research-v24.md`, `docs/research-v24-e2e.json`; modify source audit; test `tests/test_research_v24_e2e.py`.

**Interfaces:** Produce Recall@10/50, Top-1/3, abstention, PIT violations, coverage, latency, response size, request and cost metrics with real/synthetic labels.

- [ ] Write failing tests for metric denominators, missing target, stale source and lookahead detection.
- [ ] Implement deterministic reports and run the registered independent cases.
- [ ] Run a bounded real GDELT-to-index-to-candidate attempt; report unresolved honestly if identity evidence is insufficient.
- [ ] Run Ruff, complete pytest, reproducibility build, Docker and GitHub Actions; create a separate stacked PR without merge/deploy.
