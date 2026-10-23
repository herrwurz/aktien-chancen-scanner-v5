# IV Attribution V2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and test-driven development.

**Goal:** Isolate IV-path, valuation-factor, slippage and loss-rule effects in hypothetical HS5RMP research.

**Architecture:** Extend the shared model resolver with explicit IV policies, then build a separate
V2.0 orchestrator and CLI command around the unchanged V1.9 report.

**Tech Stack:** Python 3.12, Decimal, pytest, Ruff, Docker.

**Spec:** `docs/superpowers/specs/2026-10-23-iv-attribution-v20-design.md`

## Tasks

1. Add failing tests and implement constant, rolling and stress IV resolution.
2. Add failing tests and implement exact stock/time/IV/FX/residual fair-value attribution.
3. Add failing tests and implement next-open versus hold research strategies plus zero/baseline/stress slippage.
4. Add V2.0 CLI/config/docs, run full verification, create a PR against `main`, and do not merge.
