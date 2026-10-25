# HEBELTRADER-Detektiv V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable two-stage detective that identifies up to three plausible stocks from an unknown text, PDF, or image teaser without solution leakage or invented evidence.

**Architecture:** Extend the existing DetectiveService and shared FTS5 research index. Stage A fuses independent retrieval channels into a reserve of at most 50 point-in-time candidates; Stage B builds a three-state evidence matrix, clusters dependent sources, and applies frozen decision thresholds. Keep scanner output and blind-test evaluation in separate processes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite FTS5, pdfplumber, Tesseract, pytest, Ruff, Docker.

**Spec:** `docs/superpowers/specs/2026-10-25-hebeltrader-detective-v3-design.md`

## Global Constraints

- Reuse the existing SEC, GLEIF, ResearchIndex, OCR, API, UI, provenance, and provider components.
- No network access at API startup; live access remains explicit and bounded.
- Historical evidence requires a proven publication and availability timestamp; missing timestamps fail closed.
- Promotional derivative returns never become stock fundamentals or retrieval signals.
- Stock and derivative identifiers remain distinct; no product WKN may be inferred.
- Additional data/API spend stays between 0 and 20 EUR monthly; no booking is authorized.
- No production database migration, deployment, merge, trading, Immich access, or secret persistence.
- Real and synthetic benchmark results remain visibly separate.

## Review Focus

- OCR or PDF pages with partial extraction must retain per-page warnings and never claim complete extraction (Task 1 tests).
- A teaser made only of promotional claims must return `insufficiently_constrained`, not random FTS candidates (Task 2 tests).
- Reposts of one primary disclosure must count as one evidence cluster (Task 3 tests).
- Missing or later availability timestamps must prevent historical confirmation (Task 3 tests).
- Blind-test solutions must be inaccessible to the scanner process through files, mounts, paths, or environment variables (Task 5 tests).

---

### Task 1: Versioned input and atomic clue extraction

**Files:**
- Modify: `scanner/hebeltrader/detective/schemas.py`
- Modify: `scanner/hebeltrader/detective/clues.py`
- Create: `scanner/hebeltrader/detective/documents.py`
- Modify: `scanner/hebeltrader/detective/cli.py`
- Test: `tests/hebeltrader/test_detective_v3_inputs.py`

**Interfaces:**
- Produces: `extract_document(data: bytes, media_type: str, *, ocr) -> ExtractedDocument` with SHA-256 and per-page provenance.
- Produces: `extract_atomic_clues(text: str, spans: list[SourceSpan]) -> list[AtomicClue]` while retaining the legacy `extract_clues(text)` adapter.
- Extends: `DetectiveRequest` with one bounded PDF payload and schema version 3 without breaking text/image callers.

- [ ] **Step 1: Write failing input tests** for 20 MiB/40-page limits, encrypted/corrupt PDFs, mixed text/OCR pages, source spans, and equivalent CLI text/PDF/image request structures.
- [ ] **Step 2: Run `pytest tests/hebeltrader/test_detective_v3_inputs.py -q`** and confirm failures identify missing V3 contracts.
- [ ] **Step 3: Implement document extraction** with text-layer-first behavior, OCR fallback only for empty pages, and explicit page completeness/warnings.
- [ ] **Step 4: Write failing clue tests** for products, geography, financial periods, events, negation, and `1.091 %`, `1.717 %`, `2.631 %` as `promotional_derivative_return` excluded from financial metrics.
- [ ] **Step 5: Implement atomic clue extraction** with deterministic `clue_id`, category, quote, span/page, instrument scope, value/unit/period/date, polarity, method, confidence class, and manual-review flag.
- [ ] **Step 6: Run `pytest tests/hebeltrader/test_detective_v3_inputs.py tests/hebeltrader/test_detective_mvp.py -q`** and confirm both V3 and backward-compatibility tests pass.
- [ ] **Step 7: Commit** with `feat: add provenance-bound detective inputs and clues`.

### Task 2: Full-universe multi-channel candidate retrieval

**Files:**
- Create: `scanner/hebeltrader/detective/retrieval.py`
- Modify: `scanner/hebeltrader/detective/index_source.py`
- Modify: `scanner/research_index/models.py`
- Modify: `scanner/research_index/repository.py`
- Test: `tests/hebeltrader/test_detective_v3_retrieval.py`

**Interfaces:**
- Consumes: `list[AtomicClue]`, `ResearchIndex`, and an aware `as_of` timestamp.
- Produces: `retrieve_candidates(index, clues, *, as_of, limit=50) -> RetrievalReport` containing channel ranks, RRF score, frozen structured contributions, exclusions, coverage, and at most 50 hits.

- [ ] **Step 1: Write failing retrieval tests** that search every point-in-time-visible asset, cap each channel and reserve at 50, fuse with RRF `k=60`, apply the specified `+8/+20/+25/+100/+3/-25/-50` contributions, and resolve ties by stable asset ID.
- [ ] **Step 2: Add failure-mode tests** for promotional-only input, known funds, unknown instrument type, derivative WKN isolation, future identities, revisions, and incomplete market coverage.
- [ ] **Step 3: Run `pytest tests/hebeltrader/test_detective_v3_retrieval.py -q`** and confirm failures.
- [ ] **Step 4: Implement focused ResearchIndex queries and the retrieval orchestrator** without loading blind-test labels or creating a separate index architecture.
- [ ] **Step 5: Run `pytest tests/hebeltrader/test_detective_v3_retrieval.py tests/test_research_index_v24.py -q`** and confirm pass.
- [ ] **Step 6: Commit** with `feat: add full-universe teaser candidate retrieval`.

### Task 3: Point-in-time evidence verification and decisions

**Files:**
- Create: `scanner/hebeltrader/detective/verification.py`
- Modify: `scanner/hebeltrader/detective/service.py`
- Modify: `scanner/hebeltrader/detective/schemas.py`
- Test: `tests/hebeltrader/test_detective_v3_verification.py`

**Interfaces:**
- Consumes: `RetrievalReport`, atomic clues, and normalized `EvidenceRecord` values.
- Produces: `verify_candidates(...) -> list[VerifiedCandidate]` with one `confirmed|contradicted|unknown` cell per clue and provenance-linked evidence clusters.
- Produces: `decide(candidates, retrieval_status) -> DetectiveDecision` using the frozen likely/unclear/unresolved thresholds.

- [ ] **Step 1: Write failing matrix tests** for confirmed, contradicted, and unknown facts; unknown sectors must remain neutral.
- [ ] **Step 2: Write failing provenance tests** that cluster same-origin/reposted evidence within 48 hours, require distinct `origin_id` values, and exclude missing, future, or superseded `available_at` records.
- [ ] **Step 3: Write failing decision tests** for three clues/two categories/two independent clusters including primary evidence, no hard contradiction, 20-point margin, plus unclear and unresolved boundaries.
- [ ] **Step 4: Write historical-time tests** for absent publication time (`missing_publication_time`), timezone normalization, delayed filings, and current identities that lack historical proof.
- [ ] **Step 5: Run `pytest tests/hebeltrader/test_detective_v3_verification.py -q`** and confirm failures.
- [ ] **Step 6: Implement verification, clustering, transparent integer scoring, and decision logic** while leaving unsupported product/customer/market-position/market-cap clues unknown.
- [ ] **Step 7: Run `pytest tests/hebeltrader/test_detective_v3_verification.py tests/test_research_v23.py -q`** and confirm pass.
- [ ] **Step 8: Commit** with `feat: verify teaser candidates with point-in-time evidence`.

### Task 4: Shared CLI/API/UI result path and product isolation

**Files:**
- Modify: `scanner/hebeltrader/detective/service.py`
- Modify: `scanner/hebeltrader/detective/cli.py`
- Modify: `scanner/main.py`
- Modify: `scanner/templates/detective.html`
- Test: `tests/hebeltrader/test_detective_v3_interfaces.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: one schema-version-3 JSON structure for CLI and API with top three, evidence matrix, contradictions, unknowns, coverage, timestamps, and `evidence_score_not_probability`.
- Preserves: explicit product verification after stock analysis and `unresolved_product_identifier` when official terms are absent.

- [ ] **Step 1: Write failing interface tests** proving byte-equivalent normalized CLI/API results apart from `analyzed_at`, bounded response evidence, no startup networking, and explicit provider failure coverage.
- [ ] **Step 2: Write failing security tests** for escaped teaser/source content, oversized responses, stock/derivative identifier separation, and absent/unverified product WKN behavior.
- [ ] **Step 3: Run `pytest tests/hebeltrader/test_detective_v3_interfaces.py tests/test_api.py -q`** and confirm failures.
- [ ] **Step 4: Integrate the V3 pipeline into service, CLI, API, and existing escaped UI** with no duplicate orchestration path.
- [ ] **Step 5: Run the interface/API tests** and confirm pass.
- [ ] **Step 6: Commit** with `feat: expose detective v3 through shared interfaces`.

### Task 5: Leakage-proof blind benchmark

**Files:**
- Create: `scanner/hebeltrader/detective/benchmark_scan.py`
- Create: `scanner/hebeltrader/detective/benchmark_evaluate.py`
- Modify: `scanner/research_benchmark.py`
- Create: `tests/fixtures/detective-v3/inputs/manifest.json`
- Create: `tests/fixtures/detective-v3/solutions/labels.json`
- Test: `tests/hebeltrader/test_detective_v3_benchmark.py`

**Interfaces:**
- Produces: scanner command that receives only input manifest/index/output and immutable per-case rankings.
- Produces: evaluator command that receives rankings and labels, checks hashes, and emits separate synthetic/open and real metrics.

- [ ] **Step 1: Write failing process-boundary tests** proving the scanner has no solution argument, path, environment lookup, or mount dependency and rejects identifiers leaked into input text or filenames.
- [ ] **Step 2: Write failing metric tests** for Top-1, Top-3, false assignment, abstention, missing universe member, coverage, runtime, request count, and cost.
- [ ] **Step 3: Add at least ten solution-independent synthetic/open functional cases** across sectors, contradictions, insufficient evidence, and an out-of-universe company; store labels only under `solutions/`.
- [ ] **Step 4: Run `pytest tests/hebeltrader/test_detective_v3_benchmark.py -q`** and confirm failures.
- [ ] **Step 5: Implement scanner/evaluator separation, SHA manifests, leakage checks, and `insufficient_real_benchmark_coverage` when fewer than ten valid real cases exist.**
- [ ] **Step 6: Run `pytest tests/hebeltrader/test_detective_v3_benchmark.py tests/test_research_v24_e2e.py -q`** and confirm pass.
- [ ] **Step 7: Commit** with `feat: add leakage-proof detective blind benchmark`.

### Task 6: Reproducible real-material runner and documentation

**Files:**
- Create: `scripts/run_detective_v3_real.sh`
- Create: `docs/hebeltrader-detective-v3.md`
- Modify: `README.md`
- Modify: `.env.example`
- Test: `tests/hebeltrader/test_detective_v3_real_runner.py`

**Interfaces:**
- Produces: read-only Docker runner accepting explicit teaser, publication metadata, research index, and output directories; it never mounts solutions into the scanner container.
- Produces: JSON/CSV/SHA-256 reports with `pending_external_material` unless the original, publication evidence, rights status, and separate reviewed solution are present.

- [ ] **Step 1: Write failing runner tests** for read-only mounts, no secrets in arguments/reports, no network by default, stable SHA reports, and honest pending status when real material is absent.
- [ ] **Step 2: Run `pytest tests/hebeltrader/test_detective_v3_real_runner.py -q`** and confirm failures.
- [ ] **Step 3: Implement the runner and documentation** including exact Hetzner/local commands, supported sources, known market/field gaps, cost limits, and the distinction between functional and real evidence.
- [ ] **Step 4: Run the runner against the available synthetic/open fixture** and verify it labels the result as non-real; run an original only if valid material is supplied.
- [ ] **Step 5: Run the runner tests** and confirm pass.
- [ ] **Step 6: Commit** with `docs: add reproducible detective v3 acceptance flow`.

### Task 7: Full verification and pull request

**Files:**
- Modify: `docs/hebeltrader-detective-v3.md` only if verification reveals a documented limitation.
- Create: generated reports only under ignored `reports/hebeltrader/detective-v3/`.

**Interfaces:**
- Produces: one feature branch and pull request against `main`; no merge or deployment.

- [ ] **Step 1: Run focused tests** with `pytest tests/hebeltrader/test_detective_v3_*.py tests/hebeltrader/test_detective_mvp.py tests/test_research_index_v24.py tests/test_research_v24_e2e.py tests/test_api.py -q`.
- [ ] **Step 2: Run the full suite** with `pytest -q`.
- [ ] **Step 3: Run formatting and lint** with `ruff format --check .` and `ruff check .`.
- [ ] **Step 4: Build the image** with `docker compose -p aktien_chancen_scanner_v6 build` without starting or changing existing services.
- [ ] **Step 5: Run the offline benchmark twice** and assert identical stable payload SHA-256 values.
- [ ] **Step 6: Review `git diff origin/main...HEAD`** for secrets, generated originals, solution leakage, unrelated changes, and productive migrations.
- [ ] **Step 7: Commit any verification-only corrections**, push the branch, create a PR against `main`, and record exact local/GitHub Actions results plus real-material blockers without merging.
