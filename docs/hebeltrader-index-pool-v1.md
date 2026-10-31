# Index-Pool v1 (Market-Universum)

Stand: 2026-10-30.

## Zweck

Der Market-Screen rankt nicht mehr nur die 115er-Kuratierliste. Er nutzt einen
**Index-Union-Pool** (~1.100 Namen), damit Blindfälle wie Deutsche Bank (202/26)
kandidierbar sind, ohne Sektor für Sektor nachzupatchen.

## Schichten

| Schicht | Quelle | Rolle |
|---|---|---|
| Pool v1 | `scanner/hebeltrader/detective/index_pool_v1.json` | Identität (Name, Ticker, Sektor) |
| Overlay | `global_universe.json` | Structure/Layer-Tags + fehlende Kuratierten |
| Offline-Struktur | weiterhin nur `global_universe.json` | Dominance-/Layer-Shortlist |

Laden: `index_pool.market_universe_list()`. Market-Export/Rank defaults darauf.

## Indexe in der Union

| Index | Markt |
|---|---|
| S&P 500 (SPX) | USA |
| Nasdaq-100 (NDX) | USA |
| DAX | Deutschland |
| MDAX | Deutschland |
| EURO STOXX 50 (SX5E) | Eurozone |
| STOXX Europe 600 (SXXP) | Europa |
| **ATX** | **Österreich** |

Mitgliedschaft aus **öffentlichen** Constituent-Listen (Wikipedia / Nasdaq.com API).
ATX-Tickers: Wikipedia-Namen → EODHD Vienna (`.VI`; Immofinanz über Frankfurt `IMO1.F`).
Kein Tiingo. Kein EODHD-Fundamentals-Abo für die Mitgliedschaft.
EODHD bleibt der Kursprovider (EOD / PIT) für Tickers im Pool.

## Rebuild

```bash
# optional, wenn Nasdaq.com vom Builder-Host blockiert:
curl -sS -A 'Mozilla/5.0' -H 'Accept: application/json' \
  -o /tmp/ndx_nasdaq.json \
  'https://api.nasdaq.com/api/quote/list-type/nasdaq100'
INDEX_POOL_NDX_JSON=/tmp/ndx_nasdaq.json python3 scripts/build_index_pool_v1.py
```

## PIT-Export (Pool)

| Lauf | Succeeded | Coverage / as_of | Meta |
|---|---:|---:|---|
| vor Remap | 919/1045 | 904–906 | `snapshots-pit-pool-v1-2026-10-30.meta.json` |
| nach Remap v1 | 994/1044 | 979–981 | `snapshots-pit-pool-v1-remap-2026-10-30.meta.json` |
| Remap v1.1 + curated post-pass | 1009/1044 | 1007–1009 | `snapshots-pit-pool-v1-remap-2026-10-31.meta.json` |
| **pad800 (history_pad_days=800)** | **1027/1044** | **1019–1021** | `snapshots-pit-pool-v1-pad800-2026-10-31.meta.json` |

Voll-JSON gitignored unter `reports/`. Spot-Checks ok: `DBK.XETRA`, `ASSA-B.ST`, `CAP.PA`, `ENI.XETRA`, ATX.

Ticker-Remap v1.1: `index_pool_ticker_remap_v1.json` (~100+ Korrekturen; +IT LSE/XETRA,
+JP ADRs). Restlücken: delistete/M&A-Namen (Swedish Match, DS Smith, MorphoSys, …).

## Diagnose auf Pool-PIT (2026-10-30)

| Corpus | Market Top1/3/8 | Lesart |
|---|---|---|
| 27er Refs | 2 / 3 / 7 (graded 25) | Coverage ↑↑, Treffer nur leicht ↑ vs kuratiert PIT |
| Blind 202/26 | DBK kandidierbar, **nicht** Top-8 | Klasse A zu; Residual **B_chart_rank** (Score 10) |

Kein Score-Retuning. Details: `docs/examples/*-pool-pit-diagnosis-notes-2026-10-30.md`.

Market-Universum: **eine Zeile je Ticker** (SPX/NDX/Curated-Namen kollabieren; Structure/Layer vom Curated-Overlay gewinnen).

## Budget / nächste Schritte

1. Pool + Remap + PIT-Diagnose + Dedup + corpus-v1 evidence freeze.
2. Evidenz-Kanal: **26/26** named identified (provisional Costco/BASF); HT-016
   scaffold under `ht-016-blocked/` (noch ohne pub_at); PDFs 192/26 & 137/26
   via `scripts/promote_provisional_publication_at.py` — siehe
   `docs/hebeltrader-source-packets.md`.
3. PIT default pad is **800** days (`market_screen export-pit --history-pad-days`).
4. EODHD Fundamentals erst bei Bedarf für automatischen Constituent-Refresh.

Der Freeze von Blind 202/26 bleibt unverändert (kein Retuning).
