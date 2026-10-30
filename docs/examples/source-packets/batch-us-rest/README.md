# Batch US-Rest: restliche US-SEC-Fälle der 27er

Parallel zu `batch-10`. Gleiche Qualitätsgates — nicht gelockert.

## Ergebnis (named)

| Case | Ticker | Named → identified |
|---|---|---|
| HT-008 | KKR | ja (Arctos) |
| HT-017 | JPM | ja (First Republic) |
| HT-018 | JNJ | ja (Stelara/Darzalex) |
| HT-019 | SLB | ja (ChampionX) |
| HT-020 | SNPS | ja (Ansys Merger) |
| HT-022 | CEG | ja (Calpine) |
| HT-027 | TMO | ja (Clario/Solventum) |

**7/7 named** identified. Original: 0/7.

## Qualitätsgates

- ≥2 Kernhinweise, Margin ≥35, ≥5 Peers
- Peer-Leakage-Audit clean
- SEC-Pakete: kein Filing am Teaser-Kalendertag (`filed >= cutoff_date` ausgeschlossen)
- Freeze-Test: `tests/hebeltrader/test_batch_us_rest_quality.py`

Zusammen mit batch-10: **17/17** US-SEC named diagnosed. Blind 202/26 unverändert.
