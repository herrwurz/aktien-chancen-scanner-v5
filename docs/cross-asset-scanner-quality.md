# Cross-asset scanner quality contract

The stock and crypto scanners share **monitoring infrastructure**, not entry rules.
The crypto V3 DOOD miss motivates an explicit audit trail for missing universes,
late discovery, rejected candidates and follow-up outcomes.

## Common states

- `checked`: source was actually queried and results inspected.
- `rejected`: candidate or source was evaluated and excluded with a reason.
- `unavailable`: no valid evidence; must never become a "no signal" assertion.

Every check records source, observation timestamp and reason. Empty source
coverage is incomplete. Public community signals are leads, not verified
execution evidence. Private Telegram/Signal content is not accessible by default.

## Stock-specific sources

SEC EDGAR filings, corporate IR, exchange notices, verifiable market quotes,
and publicly accessible news. SEC acceptance timestamps are not equivalent to
the time the monitor first observed a filing. No order eligibility without
validated quote freshness, liquidity and explicit trading rules.

## Crypto-specific sources

DEX pools, CEX spot, derivatives as corroboration, on-chain activity,
listings/unlocks and public communities. Small-cap discovery must not depend
on top-100 futures volume. Market manipulation and survivorship bias require
separate crypto thresholds.

## Follow-up quality metrics

Record initial discovery and 1h/4h/24h due windows. Do not calculate returns
without timestamped, verified prices and the correct exchange trading calendar.
Measure missed opportunities separately from alerts and rejected candidates.
No trading actions are authorized by these monitoring modules.
