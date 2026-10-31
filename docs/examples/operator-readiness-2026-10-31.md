# Operator readiness (2026-10-31)

Single board for what still blocks production evidence work.

```bash
python3 -m scanner.hebeltrader.detective.corpus_report readiness
```

## Green

| Gate | Status |
|---|---|
| Corpus-v1 named | **26/26** identified (`historical_source_packet`) |
| Costco 192/26 + BASF 137/26 Stand | **promoted** (`publisher_pdf_stand_uhr`) |
| Shared 27er `publication_at` for HT-003/012 | filled |
| Gates (≥2 clues, margin≥35, ≥5 peers) | ok |
| Simulated Stufe 3b | harness green |
| Live API keys | EODHD / Tavily / OpenAI present |
| Active-call exclusion | wired into live Investigator (180d) |
| Corpus investigate shortcut | `--corpus-case HT-xxx` |

## Blocked / gap

| Item | Status |
|---|---|
| HT-016 | 191/26 bound 15.10.2026; **open** until Call-PDF/report |
| Original teasers | **0/27** with ≥2 native named anchors |
| Next learning case | Monday teaser before Call-PDF |

## Smoke

```bash
python3 -m scanner.hebeltrader.detective.investigate_cli analyze \
  --corpus-case HT-003 --root /tmp/ht-corpus-case
python3 scripts/promote_provisional_publication_at.py   # expect already_promoted
python3 scripts/refresh_original_anchor_gap.py
```

JSON: `operator-readiness-2026-10-31.json`.
