# Evidence-rich Teaser Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Tavily evidence through blocked source fetches and rank candidates by cited clue specificity without fabricated winners.

**Architecture:** Extend the existing Tavily adapter with archived snippets and Extract fallback, attach explicit source classes to documents, and compute deterministic clue-specific ranking weights. Mark top-score ties explicitly and render them without ordinal winner claims.

**Tech Stack:** Python, FastAPI, Tavily Search/Extract, OpenAI citation annotation, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-evidence-rich-teaser-ranking-design.md`

## Global Constraints

- Do not hardcode ASML, TSMC or any historical solution.
- Never promote a search snippet to primary evidence.
- Preserve source URL, retrieval time, content hash and temporal uncertainty.
- Keep the existing monthly budget and disabled automatic recharge.
- No merge or deployment.

## Review Focus

- Malformed or oversized Tavily content must fail closed.
- Extract failure must retain only a bounded archived snippet.
- Publisher identities must not become stock candidates.
- Equal scores must not create a claimed unique leader.
- Historical-blind runs must not use newly fetched evidence.

---

### Task 1: Tavily evidence fallback

**Files:** `scanner/hebeltrader/detective/external_research.py`, `tests/hebeltrader/test_external_research.py`

- [ ] Add failing tests for Search content retention, Extract fallback, bounded snippet fallback and source class.
- [ ] Implement archived Tavily result content and `/extract` support.
- [ ] Run focused tests and commit.

### Task 2: Specificity ranking and ties

**Files:** `scanner/hebeltrader/detective/investigation.py`, `scanner/templates/detective.html`, `tests/hebeltrader/test_primary_investigation.py`, `tests/hebeltrader/test_external_research.py`

- [ ] Add failing tests proving cited technological exclusivity outranks generic financial growth and a zero-score tie is explicit.
- [ ] Implement deterministic specificity weights and tie metadata.
- [ ] Render equal leaders without ordinal winner language.
- [ ] Run focused tests and commit.

### Task 3: Documentation and verification

**Files:** `docs/hebeltrader-detective-v3.md`, `README.md`

- [ ] Document source classes, fallback order and tie behavior.
- [ ] Run Ruff, formatting, full suite and independent review.
- [ ] Push PR #34 and verify GitHub Actions.
