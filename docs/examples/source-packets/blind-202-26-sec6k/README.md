# Blind 202/26 — SEC 6-K developmental packet (FPI)

**Freeze untouched.** Ranking-SHA256
`3fff83e1387325ccf8c1fc47d49940c5d9385244fd00518c1ea0c4722a331b0f` remains
the prospective-blind freeze. This folder is **developmental diagnosis** only.

## Why SEC 6-K (not guessed IR URLs)

Deutsche Bank IR paths were previously guessed and returned **HTTP 404**.
Verified sources used here:

| Source | Binding | Notes |
|---|---|---|
| EDGAR 6-K `0001159508-26-000044` filed **2026-10-28** | `sec_edgar_filing_date` | Exhibit 99.1 earnings body (`db20261028991.htm`), not the short cover |
| Live IR press release (reference only) | — | `https://www.db.com/news/detail/20261028-deutsche-bank-reports-on-the-third-quarter-results-of-2026` HTTP 200; **not** in the packet (no archive binding) |

Cutoff: `2026-10-30T08:15:00+01:00`. Same-day EDGAR exclusion unchanged
(`filed >= cutoff_date` out).

Peers (resolution PDF + SEC FPIs): SAN, UBS, JPM, ING, HSBC — six issuers.

## Builder change

`build_sec_packet` now accepts **6-K / 20-F**, prefers recent **6-K** over stale
**20-F** for foreign private issuers, and resolves 6-K cover pages to the largest
earnings exhibit under the same accession.

## Evidence batch

```bash
python3 -m scanner.hebeltrader.detective.evidence_batch \
  --inputs docs/examples/source-packets/blind-202-26-sec6k/BLIND-202-26.inputs.*.json \
  --source-packets docs/examples/source-packets/blind-202-26-sec6k/packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --summary docs/examples/source-packets/blind-202-26-sec6k/evidence-batch-blind-202-26.json
```

| Inputs | `packet_evidence` | `identification` |
|---|---|---|
| original clue summary | insufficient | not_identified |
| named (Konzern Deutsche Bank + DWS) | ready → **DB** | **identified** (`historical_source_packet`) |

Gates: ≥2 Kernhinweise, margin ≥35, ≥5 peer issuers checked. Original stays
not identified (no native named anchors in the blind clue summary).
