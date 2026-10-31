# Corpus-v1: unified evidence freeze (26/27 refs)

Union of all shippable source-packet batches after EU-IR + Costco/BASF
(PDF Stand confirmed). **HT-016** remains out (no issue / no date).

## Named identification

| Batch | Cases | Named identified |
|---|---:|---:|
| batch-10 | 10 | 10 |
| batch-us-rest | 7 | 7 |
| batch-eu-sec | 3 | 3 |
| batch-eu-ir-wayback | 4 | 4 |
| batch-pending-pdf | 2 | 2 (PDF Stand Uhr) |
| **corpus-v1** | **26** | **26** |

Original teasers: **0/26** identified (corpus gap: no ≥2 native named anchors).

Gates unchanged: ≥2 Kernhinweise, margin ≥35, ≥5 peer issuers,
`basis=historical_source_packet`. Blind 202/26 freeze SHA untouched.

## Cutoffs

HT-003 / HT-012 use publisher PDF Stand Uhr (`2026-10-16T08:15` /
`2026-07-31T08:15`). Shared `reference-27-inputs-with-publication-at.json`
filled. No provisional cutoffs remain in corpus-v1.

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

Operator CLI (no re-scan for scorecard/gap; tiebreak needs local pad800 JSON):

```bash
python3 -m scanner.hebeltrader.detective.corpus_report report
python3 -m scanner.hebeltrader.detective.corpus_report recipe
python3 -m scanner.hebeltrader.detective.corpus_report originals
python3 -m scanner.hebeltrader.detective.corpus_report tiebreak
python3 -m scanner.hebeltrader.detective.corpus_report readiness
```

Primary CLI replay:

```bash
python3 -m scanner.hebeltrader.detective.investigate_cli analyze \
  --corpus-case HT-001 --root /tmp/ht-corpus-case
```

Artifacts: `corpus-report.json`, `originals-gap.json`, `operator-recipe.json`.
Market tie-break: `docs/examples/market-tiebreak-pad800-2026-10-31.{json,md}`.
Readiness: `docs/examples/operator-readiness-2026-10-31.{json,md}`.
