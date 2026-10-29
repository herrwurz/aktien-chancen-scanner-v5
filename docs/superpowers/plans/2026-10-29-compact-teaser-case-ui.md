# Compact Teaser Case UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace long mobile case lists with a single-case selector, make analysis progress unmistakable, and surface the original-resolution workflow.

**Architecture:** Keep the existing API and journal model. Change only the server-rendered HTML/CSS and its browser-side rendering functions, with DOM contract tests guarding placement, visibility, and error reporting.

**Tech Stack:** Jinja HTML, CSS, browser JavaScript, FastAPI TestClient, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-compact-teaser-case-ui-design.md`

## Global Constraints

- Preserve append-only case and resolution behavior.
- Do not change ranking, research, reference data, or trading behavior.
- Optimize the controls for a mobile browser.

## Review Focus

- Empty case collection must leave a useful selector state.
- Archived filtering must use the same compact view.
- Failed JSON and non-JSON API responses must display a useful safe error.
- Selecting a case without a completed prediction must remain usable.
- Resolution shortcuts must populate only known values and focus the resolution form.

---

### Task 1: Compact case selector and resolution call to action

**Files:**
- Modify: `scanner/templates/detective.html`
- Test: `tests/test_teaser_web.py`

**Interfaces:**
- Consumes: existing `/api/hebeltrader/cases`, archive, restore, prospective, and promotion endpoints.
- Produces: `#case-select`, `#include-archived`, `#active-case`, `#resolution-panel`, and `.open-resolution` controls.

- [ ] Add failing HTML contract tests for the selector, single active-case container, prominent resolution panel, and absence of the old cases list.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement compact selection, single-case rendering, archived filtering, and resolution shortcuts.
- [ ] Run focused tests and confirm success.
- [ ] Commit the task.

### Task 2: Visible progress and actionable errors

**Files:**
- Modify: `scanner/templates/detective.html`
- Test: `tests/test_teaser_web.py`

**Interfaces:**
- Consumes: existing investigate response body and HTTP status.
- Produces: `.analysis-status.running|success|error` and safe error-detail formatting.

- [ ] Add failing contract tests for red running styling, state classes, and server-detail formatting.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement the status state helper and safe response-error extraction.
- [ ] Run focused tests and confirm success.
- [ ] Commit the task.

### Task 3: Verification and deployment

**Files:**
- Modify only if verification exposes a defect.

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: tested PR branch and explicit Coolify deployment marker.

- [ ] Run `python -m pytest -q tests/test_teaser_web.py`.
- [ ] Run `python -m pytest -q` and `ruff check .`.
- [ ] Review the final diff for secret exposure and unchanged API semantics.
- [ ] Push the branch, wait for CI, then trigger the configured Coolify deployment without merging.
