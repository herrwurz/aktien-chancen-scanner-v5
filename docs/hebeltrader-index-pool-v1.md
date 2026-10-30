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

Meta: [`docs/examples/snapshots-pit-pool-v1-2026-10-30.meta.json`](examples/snapshots-pit-pool-v1-2026-10-30.meta.json)  
Voll-JSON: gitignored `reports/snapshots-pit-pool-v1-2026-10-30.json`.

| Kennzahl | Wert |
|---|---:|
| Attempted | 1045 |
| Succeeded bars | 919 |
| Coverage / as_of | 904–906 |
| as_of dates | 27 |
| Status | partial |

Spot-Checks ok: `DBK.XETRA`, ATX (`EBS.VI`, `BG.VI`, `POST.VI`, …).  
~126 Ticker-Map-Fehler (Share-Classes/Lokal-Suffixe, z. B. Schweden/Italien/UK) → Follow-up, kein Sektor-Patch.

```bash
python3 -m scanner.hebeltrader.detective.market_screen export-pit \
  reports/snapshots-pit-pool-v1-2026-10-30.json \
  --inputs docs/examples/reference-27-inputs.json
```

## Budget / nächste Schritte

1. Pool + ATX committed → **0 € Extra**.
2. PIT-Meta committed; Voll-JSON lokal unter `reports/`.
3. Ticker-Normalisierung für Share-Classes verbessern (Coverage ↑).
4. EODHD Fundamentals (~60 $/Mo) erst wenn automatischer Constituent-Refresh den
   manuellen Quartals-Rebuild klar schlägt.

Der Freeze von Blind 202/26 bleibt unverändert (kein Retuning). Der Pool behebt die
Universums-Lücke für **künftige** Fälle.
