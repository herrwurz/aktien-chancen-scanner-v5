# Corpus-v1: unified evidence freeze (26/27 refs)

Union of all shippable source-packet batches after EU-IR + provisional
Costco/BASF. **HT-016** remains out (no issue / no date).

## Named identification

| Batch | Cases | Named identified |
|---|---:|---:|
| batch-10 | 10 | 10 |
| batch-us-rest | 7 | 7 |
| batch-eu-sec | 3 | 3 |
| batch-eu-ir-wayback | 4 | 4 |
| batch-pending-pdf | 2 | 2 (provisional cutoff) |
| **corpus-v1** | **26** | **26** |

Original teasers: **0/26** identified (corpus gap: no ≥2 native named anchors).

Gates unchanged: ≥2 Kernhinweise, margin ≥35, ≥5 peer issuers,
`basis=historical_source_packet`. Blind 202/26 freeze SHA untouched.

## Provisional cutoffs

HT-003 / HT-012 still use `featured_date + Stand 08:15` until PDFs **192/26**
and **137/26** land. Shared `reference-27-inputs-with-publication-at.json`
stays `null` for those two.

## Commands

```bash
python3 -m scanner.hebeltrader.detective.evidence_batch \
  --inputs docs/examples/source-packets/corpus-v1/HT-*.inputs.*.json \
  --source-packets docs/examples/source-packets/corpus-v1/packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-31.json \
  --summary docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json
```

Freeze: `evidence-batch-corpus-v1.json`. Quality:
`tests/hebeltrader/test_corpus_v1_quality.py`.
