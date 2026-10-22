# Historical stock data source decision — Issue #4 / PR5

Reviewed: **22 October 2026**. Budget considered: **EUR 0–20 per month**.

## Decision

Use explicit, locally supplied **licensed CSV** as the first historical-data path. No online provider is approved or activated by this review. This is a practical scope decision: the public documentation below does not establish correct identity, venue, historical coverage, adjustment compatibility and usage rights for all **118 existing recommendations**. A broad exchange count is not a coverage audit of those recommendations.

No market-data API requests, data purchases, subscriptions, production access or production changes were made for this assessment. Public documentation was researched; no historical price dataset was downloaded. Therefore no provider success rate or empirically verified coverage is claimed.

## Candidate evaluation

| Candidate | Official evidence | Assessment for this backtest |
| --- | --- | --- |
| Yahoo Finance through yfinance | [yfinance's own disclaimer](https://ranaroussi.github.io/yfinance/) says it is unaffiliated with Yahoo, intended for research/education, and describes Yahoo's API as personal-use-only. It explicitly directs users to [Yahoo's terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). A library's availability does not grant rights to the underlying prices. | Reject as an automatic default. Personal research may be possible under applicable terms, but this review establishes neither permission for the application's intended use/redistribution nor complete delisted history and WKN-to-venue mapping. No undocumented endpoint or scraping workaround is introduced. |
| Alpha Vantage | [Support](https://www.alphavantage.co/support) states a standard free limit of **25 requests/day**. [API documentation](https://www.alphavantage.co/documentation/) describes raw daily OHLCV, adjusted close and split/dividend events; daily `outputsize=compact` returns 100 observations, while full daily history requires premium access. [Terms](https://www.alphavantage.co/terms_of_service/) grant personal, non-commercial use unless otherwise agreed in writing. | Reject the free tier for a reproducible, longer-history 118-recommendation batch. Even assuming just one request per distinct instrument, a large universe can exceed the daily quota; identity/action checks add requests. Compact history is not a substitute for the required historical interval. Premium price and actual coverage were not verified, so no claim is made that a suitable paid plan fits EUR 20. |
| EODHD | [Pricing](https://eodhd.com/pricing) lists the free Sandbox with one year of history and Historian / EOD Historical All-World at **USD 19.99/month**, or USD 199/year. [Historical API documentation](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes) distinguishes adjusted close from other price fields and links corporate-action APIs. [Delisted documentation](https://eodhd.com/financial-apis/delisted-stock-companies-data-2) documents finding delisted symbols and querying their historical prices. | Stronger candidate for a later controlled trial, but not selected now. USD pricing is not a verified EUR checkout cost, and tax/FX, relevant entitlements and commercial/storage/export rights remain unverified. Neither the free history nor general all-world/delisted claims prove the required intervals for these 118 recommendations. No plan was activated. |

Prices and entitlements can change. The quoted EODHD price is a published USD list price on the review date, not an approved purchase, a conversion to EUR or a contractual offer. The annual option requires an annual payment; its monthly equivalent is not a monthly budget commitment.

## Identity, session and adjustment requirements

CSV is a transport format, not a license. A user-supplied file must still have documented rights for the intended processing, retention and sharing. Keep licensed vendor data out of the repository unless redistribution is explicitly permitted.

Before treating any file as usable evidence, record and review:

- **Identity:** explicit source WKN and, where available, ISIN; vendor symbol; venue/MIC; currency; and the effective historical identifier interval. Do not infer a ticker from a company name, or assume one ISIN selects one listing. Unknown or ambiguous mapping remains UNKNOWN.
- **Session:** exchange timezone, bar frequency, trading-session/date convention and the covered period. Daily bar dates need a documented session interpretation; do not invent an intraday availability timestamp. EODHD's [exchange-hours documentation](https://eodhd.com/financial-apis/exchanges-api-trading-hours-and-stock-market-holidays) demonstrates that timezone/calendar metadata is a separate concern from prices.
- **Corporate actions:** raw versus split/dividend adjustment policy for every OHLC field and volume; splits, dividends, symbol changes and merger handling. PDF stock entry/stop/target levels must be on the same basis as bars. Never compare raw targets directly with adjusted-close values or silently mix differently adjusted OHLC fields. Alpha Vantage's [adjustment explanation](https://www.alphavantage.co/support) and EODHD's [historical API explanation](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes) show why vendor fields need explicit interpretation.
- **History quality:** missing sessions, duplicate timestamps, impossible OHLC values, currency changes, suspensions and delisting/end-of-history treatment. A missing bar is not evidence of a failed recommendation. EODHD's [delisted symbol example](https://eodhd.com/financial-apis/delisted-stock-companies-data-2) permits a null ISIN; even vendor metadata does not remove manual identity checks.
- **Provenance:** source/export reference, retrieval date, license evidence, immutable file checksum and exact coverage range. Freeze the input used for a run: EODHD documents that dividend-adjusted closes can be recalculated as subsequent dividends occur.

These are admission/review requirements, not a claim that the current CSV reader automatically validates every item. The current run must report usable, missing and rejected mappings separately, with reasons, before interpreting aggregate results.

## Gate for a later provider integration

Create a per-instrument coverage matrix for the 118 recommendations: WKN/ISIN, selected historical listing and currency, required interval, available interval, raw/adjusted policy, corporate actions, delisted status, license and estimated total cost. Obtain sample exports under an appropriate entitlement and check them against the source documents and session calendar. Only then choose a provider and authorize any paid activation. Until that evidence exists, offline licensed CSV keeps the experiment explicit and reproducible without pretending that absent prices are verified outcomes.
