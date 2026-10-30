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
| **nach Remap v1** | **994/1044** | **979–981** | `snapshots-pit-pool-v1-remap-2026-10-30.meta.json` |

Voll-JSON gitignored unter `reports/`. Spot-Checks ok: `DBK.XETRA`, `ASSA-B.ST`, `CAP.PA`, `ENI.XETRA`, ATX.

Ticker-Remap v1: `index_pool_ticker_remap_v1.json` (~76 Korrekturen).  
Restlücken: Japan `.TSE`, Italien `.MI` ohne Venue, delistete/illiquide Namen.

## Budget / nächste Schritte

1. Pool + Remap + PIT-Coverage ↑ → **0 € Extra**.
2. Diagnose Refs/Blind auf Pool-PIT (ohne Score-Retuning von 202/26).
3. Evidenz-Kanal (Quellenpakete) vor teuren API-Upgrades.
4. EODHD Fundamentals erst bei Bedarf für automatischen Constituent-Refresh.

Der Freeze von Blind 202/26 bleibt unverändert (kein Retuning).
