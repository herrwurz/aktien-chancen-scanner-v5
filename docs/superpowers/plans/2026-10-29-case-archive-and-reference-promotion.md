# Case Archive and Reference Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Archive two obsolete test cases without breaking the journal and promote a resolved prospective blind case explicitly into a separate reference register.

**Architecture:** Add append-only lifecycle events to `CaseJournal`, expose authenticated API actions, and render archive/promotion controls in the existing detective page. Keep historical development references, active cases, archived cases, and prospective references distinct in state and quality output.

**Tech Stack:** Python, FastAPI, JSONL hash-chain journal, vanilla JavaScript, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-case-archive-and-reference-promotion-design.md`

## Global Constraints

- Never rewrite or delete journal events.
- Archive exactly `TI-d2dbb1445c2dd2d9202a` and `TI-c49541d04ed87748f7b8` after deployment.
- Keep `TI-22d214ce388b332dfbf9` active as `prospective_blind` until a sourced resolution exists.
- Keep purchased PDFs private; no PDF content enters the repository.
- Do not merge or deploy.

## Review Focus

- Repeated archive and promotion requests must be idempotent.
- Unknown IDs must fail without appending an event.
- Unresolved cases must not be promotable.
- Archived cases must remain integrity-verifiable and retrievable explicitly.
- Quality metrics must exclude archived cases and label prospective references separately.

---

### Task 1: Append-only lifecycle events

**Files:**
- Modify: `scanner/hebeltrader/detective/case_journal.py`
- Test: `tests/hebeltrader/test_case_journal.py`

**Interfaces:**
- Produces: `archive(case_id, reason)`, `promote_reference(case_id, source)`, `cases(include_archived=False)` and state fields `archived`, `evaluation_class`, `reference_status`.

- [ ] Add failing tests for archive integrity, idempotency, unknown IDs, resolution prerequisite and promotion idempotency.
- [ ] Run the focused journal tests and confirm failure.
- [ ] Implement the minimal append-only events and derived state.
- [ ] Update `quality()` to exclude archived cases and separate prospective references.
- [ ] Run focused tests and commit.

### Task 2: Authenticated API and web controls

**Files:**
- Modify: `scanner/main.py`
- Modify: `scanner/templates/detective.html`
- Test: `tests/test_teaser_web.py`

**Interfaces:**
- Consumes: Task 1 journal methods.
- Produces: authenticated archive, archived-list and reference-promotion endpoints plus user-visible controls.

- [ ] Add failing endpoint tests for authentication, exact-ID archive, archived listing and rejected unresolved promotion.
- [ ] Run focused web tests and confirm failure.
- [ ] Implement endpoints using the existing case-access token.
- [ ] Add archive view and promotion button without exposing PDF content.
- [ ] Run focused tests and commit.

### Task 3: Documentation and full verification

**Files:**
- Modify: `docs/hebeltrader-detective-v3.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1–2 behavior.
- Produces: operator steps for the two archives and later Fall-19 promotion.

- [ ] Document archive semantics, prospective blind resolution and explicit promotion.
- [ ] Run Ruff, formatting checks and the complete test suite.
- [ ] Verify the PR diff contains no secrets, PDF content, deployment or merge.
- [ ] Commit, push to PR #34 and verify GitHub Actions.
