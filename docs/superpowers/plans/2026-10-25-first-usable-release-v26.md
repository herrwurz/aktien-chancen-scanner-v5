# Scanner V6 First Usable Release – V2.6 Plan

**Goal:** Expand the proven V2.5 market-data path from the nine-stock pilot to a controlled,
auditable US universe without weakening identity, point-in-time, licensing or budget gates.

## Scope and constraints

- Reuse the SEC index, Tiingo collector, immutable raw cache and revisioned SQLite archive.
- Never start network access implicitly. Each live batch requires both network and provider-usage
  authorization, a renewed token supplied only at runtime, and a persistent quota reservation.
- Keep the free-provider limits conservative and configurable downward; never claim a live result
  from fixtures or cached test data.
- Keep the benchmark outside the operating-company candidate universe.
- No deployment, production database changes, paid booking, automatic order or merge.

## Implementation

- [x] Add deterministic, non-overlapping SEC-universe pages and expose total eligible coverage.
- [x] Add a tamper-evident quota ledger with hourly, daily and monthly-symbol hard stops.
- [x] Add an overlapping correction window and report archive-wide sessions/actions/revisions.
- [x] Add isolated benchmark collection and preserve its non-candidate role in provenance.
- [x] Add an isolated Docker runner for 100 stocks in bounded batches and canonical JSON/CSV/SHA
      reports, with safe resume after provider failure.
- [x] Document official-calendar input requirements, Tiingo rights/limits and lawful issuer-feed
      boundaries. Unknown rights remain blocked.
- [x] Add offline regression tests for pagination, quota exhaustion, corrections, retries,
      idempotent resume, benchmark separation and point-in-time visibility.
- [ ] Run Ruff, pytest and Docker build; publish a PR with an explicit live-acceptance blocker until
      the Hetzner run supplies real report hashes.

