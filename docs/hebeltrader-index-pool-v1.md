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

SPX, Nasdaq-100, DAX, MDAX, EURO STOXX 50, STOXX Europe 600.

Mitgliedschaft aus **öffentlichen** Constituent-Listen (Wikipedia / Nasdaq.com API).
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

## Budget / nächste Schritte

1. Pool committed → **0 € Extra**.
2. PIT-/Snapshot-Export auf dem Pool (~1.1k Tickers, 1 Call/Ticker) bei Bedarf.
3. EODHD Fundamentals (~60 $/Mo) erst wenn automatischer Constituent-Refresh den
   manuellen Quartals-Rebuild klar schlägt.

Der Freeze von Blind 202/26 bleibt unverändert (kein Retuning). Der Pool behebt die
Universums-Lücke für **künftige** Fälle.
