# Scanner V6 First Usable Release – PR #22 P0 Plan

**Goal:** Close review findings #5642491870 and #5642508963 on PR #22 before any wider-universe follow-up branch.

## Constraints

- Keep work in PR #22; no merge, deployment, provider booking, production database or Immich changes.
- Real Hetzner artifacts remain read-only and licensed raw data stays off Git.
- Adjusted data drives comparable returns; raw USD data drives liquidity and displayed risk levels.
- A missing real server run remains an explicit blocker rather than a fixture success.

## Tasks

- [x] Add raw/adjusted scale regressions and compute raw USD turnover plus raw-scale, non-executable risk levels.
- [x] Unify bar/news cutoff metadata and reject invalid signal/as-of combinations.
- [x] Bind the scanner run to the SHA-verified V2.5.1 coverage and surface PXED/VOGX/incomplete rows.
- [x] Harden the isolated Docker runner against overlapping paths and verify input SHA before analysis.
- [x] Extend coverage/ranking audit fields without inventing market-wide coverage.
- [ ] Run focused and full regression checks, update PR #22 and wait for GitHub Actions.
- [ ] Run the real Hetzner offline scan when server access is available; record only aggregate results and SHAs.

The larger 100+ universe, current incremental collection, official calendar, benchmark and continuous
news ingestion belong in the follow-up PR only after PR #22 review/merge approval.
