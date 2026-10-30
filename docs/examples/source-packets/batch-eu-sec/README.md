# Batch EU-SEC: FPI issuers with EDGAR listings

Parallel SEC **6-K** packets for remaining reference cases that (1) have
`publication_at` and (2) file with the SEC as foreign private issuers.

No guessed IR URLs. Zurich / Thales / Leonardo SpA / Adidas have **no** SEC
issuer CIK — covered separately in `batch-eu-ir-wayback/` (Wayback IR + SEC
peers). Costco / BASF still lack `publication_at` for HT-003 / HT-012.

## Ergebnis (named)

| Case | Ticker | Named anchors | identified |
|---|---|---|---|
| HT-014 | SAP | Dremio + Prior Labs / S/4HANA | ja |
| HT-021 | BP | Castrol (+ Konzern BP) | ja |
| HT-024 | E (Eni) | Plenitude | ja |

**3/3 named** identified via `historical_source_packet`. Original: 0/3.

## Builder notes

- Needle-guided 6-K pick uses distinctive product needles only (not generic
  `buyback`/`dividend`) so AGM wrappers do not beat earnings packages.
- Konzern cue accepts short tickers (`BP`).
- Adjacent `Wachstumstreiber` wins over a distant earlier `Übernahme` hit.
