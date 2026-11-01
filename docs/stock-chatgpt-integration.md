# Stock monitor ↔ ChatGPT: integration contract and rollout

**Scope:** stock monitor only. The HEBELTRADER detective is owned by Cursor and MUST NOT be modified or exposed through this integration. No changes to crypto services without a separate review.

## Architecture decision
1. GitHub repo is the **source code**; Hetzner worker + persistent journal/database is the **runtime source of truth**.
2. ChatGPT is the **analyst and QA consumer**, not a second authoritative live signal engine. Until a supported authenticated connector is configured, scheduled ChatGPT tasks remain separate and MUST say they have not read Hetzner data.
3. Use the pure, offline `scanner.stock_monitor.export.export_runs` function to produce a validated JSON snapshot. This is not a deployed API. It returns `partial` for research-only runs, `unavailable` for absent journal and raises on checksum errors.
4. Future read-only HTTP API must expose only scoped stock data: `GET /v1/stock/runs`, `GET /v1/stock/events`, `GET /v1/stock/quality/weekly`. Add authenticated access, rate limits, cursor pagination, maximum response size, audit logging, TLS, secret rotation and redaction. No write/order endpoints.
5. Never expose PostgreSQL, Docker, raw provider credentials, licensed historical data or HEBELTRADER files to ChatGPT. Before publishing any API, check provider redistribution terms; prefer metadata and source links over proprietary OHLCV payloads.

## Signal ownership
- Ingestion/dedup/quote provenance and preliminary classification: server.
- Deeper counter-research and explanatory report: ChatGPT only after reading the **same** server run IDs and evidence cutoff.
- Server controls alert deduplication. A ChatGPT-only hypothesis is `independent_research`, never a server-confirmed trade.
- No fabricated entries, fills, returns, hit rates or complete market coverage.
- Every reported candidate includes source time, first-seen time, last verified quote time and explicit unknowns.

## Rollout gates
A. Merge the isolated journal/export only after CI and review.
B. SEC read-only adapter with valid identification/User-Agent, licensing, caching, backoff and evidence receipts; test replay and failure cases.
C. Stock worker scheduler, official exchange calendar, data coverage and verified instrument identities; preserve existing crypto worker.
D. Quote provenance, spread/fee/gap gates, paper-only validation; no orders.
E. Secure read-only API; threat model, secret provisioning, staging test; no public deployment without approval.
F. Explicitly connect an authorized ChatGPT connector/app capable of fetching this API; verify real returned run IDs and cutoff. If no supported connector exists, do **not** claim integration; use manually exported snapshots or connected GitHub artifacts as an interim, clearly labeled delayed workflow.
G. Only after verified end-to-end integration, revise the existing ChatGPT automation to reference server runs and prevent duplicate alerts. Keep independent web discovery as a separate QA lane.
H. Run 2–4 weeks shadow mode, reconcile alerts/misses against immutable journals, measure data completeness and latency before any production alert switch.

## Acceptance
- A run appears once with stable `run_id`, code SHA, source URL, UTC publication/first-seen/retrieval/cutoff, source hash, reason and decision status.
- Corrupt/missing/stale data fail closed; EOD is never labeled executable.
- Weekly quality report cites real run IDs and primary sources; coverage denominators and missing logs visible.
- Regression CI green; changed paths contain no `scanner/hebeltrader/` or `tests/hebeltrader/` files.
- No auto-merge, server change, credentials or trade execution.
