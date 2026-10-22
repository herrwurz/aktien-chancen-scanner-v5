# HEBELTRADER Backtest V1 — Issue #4

## Scope
Experimental, **offline-only stock OHLC simulator**, database access in PostgreSQL READ ONLY. No scraping, market APIs, actual order execution, production migrations, or mutation of `hebel_outcomes`. Existing 118 V2.1 recommendations remain unchanged. Every archived folder label is ignored as an outcome.

## Example
Create `mapping.json` with explicit WKN identification, e.g.
```json
{"A1W4U4":{"file":"antero.csv","venue":"NYSE","currency":"USD","adjustment":"raw"}}
```
CSV column header: `timestamp,open,high,low,close`; ISO timestamps with timezone. OHLC data must be accurately sourced, venue/timezone aligned, and appropriate for the prices/targets in the PDF. Incorrect currency/split adjustment gives invalid outputs.

With DATABASE_URL configured:
```bash
python -m scanner.hebeltrader.backtest_cli --bars-dir /input/ohlc --map /input/mapping.json --as-of 2026-10-22T00:00:00+00:00 --output /tmp/backtest.json
```
Mapping entry absent -> UNKNOWN, never guessed. No OHLC files are included. No derivative prices or market history have yet been fetched. No empirically verified success rate can be claimed.

## Limitations / next PR
- The engine uses next available bar open as indicative stock entry, not historical filled orders. It records a modeled percent return, **not realized performance**.
- For daily OHLC when stop and target coexist in a bar, status is ambiguous. Gaps use the observed opening price. Target 1 and target 2 in same candle are ambiguous.
- Pending documents can be replayed for research, but **must not be promoted to verified training labels** without review and evidence of publication availability.
- Corporate action treatment, venue/session calendars, historical availability, ticker/WKN normalization, delisting, spread, commissions and derivative bid/ask series require upstream verified data and/or future modules. Currency or adjustment mismatches must be handled before interpreting an output.
- Finite observation periods result in `not_triggered` or `target1_open`, not confirmed success.
- Provider decision: start with *offline licensed or user-provided CSV*, cost EUR 0; implement historical data provider integrations only after source/terms/coverage audit. Avoid a free API that silently mixes venue, delisted symbols and adjusted prices.
- Run the unit tests via `python -m pytest tests/test_hebel_backtest.py -q`.

## Caveats before operational use
Conservative `available_at` fallback is next calendar day Europe/Berlin; any recommended 20-day closure or rule-specific stop adjustment is **not yet automated**. `stock_stop2` is used as a supplied second stop where available, otherwise an entry-price approximation; first-bar partial fills may differ. This is a limited baseline engine, **not a full HEBELTRADER rules backtest**. Additional intraday sequencing, commission model, data provenance checks and rule parsing are required before calibrating signals.

No Hetzner changes made.
