# Two-stage OpenAI Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split repeated source extraction from higher-quality teaser planning and final review, with per-model usage reporting.

**Architecture:** Add validated extraction and reasoning settings, route API tasks by role, and keep final review advisory. Derive usage and cost estimates from archived provider usage grouped by the actual request model.

**Tech Stack:** Python, Pydantic Settings, OpenAI Chat Completions, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-two-stage-openai-models-design.md`

## Global Constraints

- No secret or API response body may reach user-visible diagnostics.
- No model output may become primary evidence or an automatic identification.
- Preserve the monthly budget gate and historical-blind isolation.
- Unknown model prices must not be estimated.

## Review Focus

- Reasoning failure still returns deterministic results.
- Invalid model names fail before network access.
- Usage is charged to the actual model from each audit record.
- Historical-blind runs make no reasoning call.
- Advisory review cannot reorder a deterministic tie.

---

### Task 1: Model roles and routing

**Files:** `scanner/config.py`, `scanner/hebeltrader/detective/external_research.py`, `tests/hebeltrader/test_external_research.py`

- [ ] Add failing tests for model-specific planning, extraction and final review calls.
- [ ] Add validated settings and route `_json` by role.
- [ ] Add an advisory final review with strict output validation and graceful failure.
- [ ] Run focused tests and commit.

### Task 2: Usage visibility

**Files:** `scanner/hebeltrader/detective/provider_usage.py`, `scanner/web.py`, `scanner/templates/detective.html`, `tests/test_teaser_web.py`

- [ ] Add failing tests for per-model token and tariff grouping.
- [ ] Show configured roles and per-model usage in runtime and analysis output.
- [ ] Document Coolify variables and run all checks.
