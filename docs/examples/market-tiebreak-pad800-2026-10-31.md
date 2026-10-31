# Market tie-break on pad800 PIT (2026-10-31)

Charts remain **suggestion / tie-break only**. Named packet evidence (Stufe 3a)
is the identification channel. Blind 202/26 freeze SHA and chart weights are
**unchanged**.

## Corpus originals (26, expected tickers)

| | graded | Top1 | Top3 | Top8 |
|---|---:|---:|---:|---:|
| pad800 PIT | 26 | 2 | 3 | 7 |
| prior remap Dedup (2026-10-30) | 25 | 2 | 3 | 7 |

Same hit ceiling — deeper history pad does not lift original-teaser chart recall.

## Named packet leaders vs market Top-8

| | count |
|---|---:|
| Named identified (3a) | 26 |
| Market Top-8 confirms packet leader | **7** |
| Market misses leader | 19 |

Market does **not** substitute for packet evidence.

## Original packet_evidence gap

| status | count |
|---|---:|
| insufficient_evidence | 25 |
| partial_evidence (HT-023 AbbVie `issuer_literal`) | 1 |
| identified | **0** |

## Blind 202/26

| | |
|---|---|
| DBK rank / score | **565** / 10 |
| In Top-8 | no |
| Residual | `B_chart_rank` |
| Snapshots used | `snapshots-pit-pool-v1-remap-2026-10-30.json` (has as_of 2026-10-30; pad800 corpus dates stop at 10-29) |

## Commands

```bash
python3 -m scanner.hebeltrader.detective.corpus_report tiebreak \
  --out docs/examples/market-tiebreak-pad800-2026-10-31.json
python3 -m scanner.hebeltrader.detective.corpus_report originals
python3 -m scanner.hebeltrader.detective.corpus_report recipe
```

JSON: `market-tiebreak-pad800-2026-10-31.json`.
