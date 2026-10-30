# 27er-Referenz: Pool-PIT-Diagnose (2026-10-30), ohne Retuning

Quelle: `case_diagnose` mit Remap-Pool-PIT
(`reports/snapshots-pit-pool-v1-remap-2026-10-30.json`, Meta committed).
Treffer gegen `data/hebeltrader/teaser-cases.json` — Entwicklungsdiagnostik, kein
unabhängiger Blind-Benchmark. Keine Algorithmusänderung.

## Market-Hypothesen (Top-8)

| Lauf | suggestion_cases | Top1 | Top3 | Top8 | graded | coverage |
|---|---:|---:|---:|---:|---:|---:|
| kuratiert PIT (vorher) | 26 | 2 | 2 | 6 | 25 | 106–107 |
| **Pool-PIT Remap** | 26 | 2 | 3 | 7 | 25 | **979–981** |

Pool-Hits: HT-003 Costco #1, HT-001 ADI #1, HT-023 AbbVie #3, HT-014 SAP #4,
HT-005 MU #5, HT-002 Zurich #6, HT-020 SNPS #6.

## Lesart

- Coverage-Sprung (~107 → ~980) schließt Universumslücken; Top-8-Treffer steigen nur leicht.
- Chart-only bleibt schwach: die meisten Refs fehlen weiterhin in Top-8.
- Blind 202/26 parallel: Klasse A geschlossen, Residual **B_chart_rank** (siehe Blind-Notes).
- Evidenz-Scanner / Quellenpakete bleiben der nächste produktive Hebel — nicht Score-Retuning.

Artefakte: `reference-27-diagnosis-pool-pit.{json,md}`.
