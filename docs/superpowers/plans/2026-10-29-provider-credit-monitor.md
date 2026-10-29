# Provider Credit Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add truthful Tavily credit monitoring and local OpenAI token/cost estimates to the protected teaser UI.

**Architecture:** A small provider-usage module fetches and validates Tavily usage with a short cache and summarizes archived OpenAI usage. The protected runtime endpoint combines those values with the existing local budget ledger; the existing page renders provider allowance separately from the EUR safety reservation.

**Tech Stack:** Python 3.12, httpx, SQLite/JSON audit files, FastAPI, vanilla JavaScript, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-provider-credit-monitor-design.md`

## Global Constraints

- Never expose provider keys or raw provider error bodies.
- Provider monitoring failures must not block teaser analysis.
- Keep the scanner's EUR 5 reservation limit unchanged.
- Label OpenAI values as local estimates and link to the billing dashboard for account balance.

## Review Focus

- Malformed Tavily responses return an unavailable state.
- Tavily network failures do not fail the runtime endpoint.
- Cached usage avoids repeated provider calls.
- OpenAI audit files with malformed or missing usage are ignored.
- No secret appears in API responses or rendered HTML.

---

### Task 1: Provider usage summaries

**Files:**
- Create: `scanner/hebeltrader/detective/provider_usage.py`
- Test: `tests/hebeltrader/test_provider_usage.py`

**Interfaces:**
- Produces: `TavilyUsageMonitor.snapshot(api_key: str) -> dict` and `summarize_openai_usage(audit_root: Path) -> dict`.

- [ ] Write failing tests for valid, malformed, failed, cached and secret-safe Tavily responses and for valid/malformed OpenAI usage archives.
- [ ] Run the focused tests and confirm feature-related failures.
- [ ] Implement validated provider summaries and a five-minute Tavily cache.
- [ ] Run focused tests and confirm they pass.

### Task 2: Protected runtime API and page

**Files:**
- Modify: `scanner/web.py`
- Modify: `scanner/templates/detective.html`
- Test: `tests/test_teaser_web.py`

**Interfaces:**
- Consumes: provider summaries from Task 1.
- Produces: `provider_credits` in `/api/hebeltrader/runtime` and rendered provider status cards.

- [ ] Write failing endpoint and HTML tests for Tavily remaining credits, OpenAI estimates and unavailable states.
- [ ] Run focused tests and confirm feature-related failures.
- [ ] Add the runtime payload and render provider allowance separately from internal reservations.
- [ ] Run focused tests and confirm they pass.
- [ ] Run the full test suite, Ruff and browser JavaScript syntax checks.
- [ ] Commit and update PR #34.
