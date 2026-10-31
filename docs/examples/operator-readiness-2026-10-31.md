# Operator readiness (2026-10-31)

Single board for what still blocks production evidence work.

```bash
python3 -m scanner.hebeltrader.detective.corpus_report readiness
```

## Green

| Gate | Status |
|---|---|
| Corpus-v1 named | **26/26** identified (`historical_source_packet`) |
| Gates (≥2 clues, margin≥35, ≥5 peers) | ok |
| Simulated Stufe 3b | harness green (`simulated_falsification`) |
| Corpus investigate shortcut | `--corpus-case HT-xxx` |

## Blocked / gap

| Item | Status |
|---|---|
| PDFs Costco **192/26**, BASF **137/26** | missing → provisional cutoffs |
| HT-016 | no issue/date (scaffold only) |
| Original teasers | **0/26** with ≥2 native named anchors |
| Live Stufe 3b | needs Tavily/OpenAI |

## Smoke

```bash
python3 -m scanner.hebeltrader.detective.investigate_cli analyze \
  --corpus-case HT-001 --root /tmp/ht-corpus-case
```

JSON: `operator-readiness-2026-10-31.json`.
