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
| Corpus investigate shortcut | `--corpus-case HT-xxx` |
| HT-016 | **dropped** from active register (2026-10-31) |

## Blocked / gap

| Item | Status |
|---|---|
| Original teasers | **0/26** with ≥2 native named anchors |
| Live Stufe 3b | needs Tavily/OpenAI in Cursor environment Secrets |

## Smoke

```bash
python3 -m scanner.hebeltrader.detective.investigate_cli analyze \
  --corpus-case HT-003 --root /tmp/ht-corpus-case
python3 scripts/promote_provisional_publication_at.py   # expect already_promoted
```

JSON: `operator-readiness-2026-10-31.json`.

## Live board

```
operator readiness
  corpus named: 26/26 (gates_ok=True)
  corpus originals: 0/26
  provisional pub_at: —
  HT-016: dropped (dropped from active register)
  API keys: EODHD_API_TOKEN=yes, TAVILY_API_KEY=no, OPENAI_API_KEY=no
  blockers (2):
    - [corpus_gap] original_teaser_anchor_gap: 0/26 originals have ≥2 native named anchors
    - [blocked] live_3b_api_keys: Tavily/OpenAI absent; use simulated_falsification offline
  next:
    - For live Stufe 3b: set TAVILY_API_KEY and/or OPENAI_API_KEY in the Cursor Cloud Agent environment Secrets
    - Secure next real teaser before reading Call-PDF (≥2 named anchors)
  pad800 market Top1/3/8: 2/3/7 of 26
```
