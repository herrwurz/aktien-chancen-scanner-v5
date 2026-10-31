# Weg zum Ticker-Ergebnis

Stand: 2026-10-30.

## In einem Satz

**Teaser mit ≥2 harten Ankern + datiertes IR/SEC-Paket (≥5 Peer-Emittenten)
→ `identification=identified` (`basis=historical_source_packet`);
Live-Falsifikation bleibt für den öffentlichen Web-Pfad.**

## Stufen

| Stufe | Signal | Bedeutung |
|---|---|---|
| 0 | `market_hypotheses` | Chart/Sektor, unverifiziert |
| 1 | `packet_evidence=partial_evidence` | 1 Kernhinweis (z.B. Emittentenname) |
| 2 | `packet_evidence=ticker_hypothesis_ready` | ≥2 Kernhinweise, klarer Vorsprung |
| 3a | `identification=identified` / `basis=historical_source_packet` | Offline-Paket mit ≥5 Peers |
| 3b | `identification=identified` / `basis=live_falsification` | Live-Suche + Gegenprüfung |

## Batch-Lauf (Piloten)

```bash
python3 -m scanner.hebeltrader.detective.evidence_batch \
  --inputs docs/examples/source-packets/pilot/HT-001.inputs.json \
            docs/examples/source-packets/pilot-original-anchors/HT-023.inputs.original.json \
            docs/examples/source-packets/pilot-original-anchors/HT-023.inputs.named.json \
            docs/examples/source-packets/pilot-named/HT-027.inputs.original.json \
            docs/examples/source-packets/pilot-named/HT-027.inputs.named.json \
            docs/examples/source-packets/pilot-ht-009/HT-009.inputs.original.json \
            docs/examples/source-packets/pilot-ht-009/HT-009.inputs.named.json \
  --source-packets /path/to/combined-packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --summary docs/examples/source-packets/evidence-batch-pilots-2026-10-30.json
```

Ergebnis (Freeze `evidence-batch-pilots-2026-10-30.json`):

| Inputs | `packet_evidence` | `identification` |
|---|---|---|
| HT-001 original | insufficient | not_identified |
| HT-023 original | partial → **ABBV** | not_identified |
| HT-023 named (Skyrizi/Rinvoq) | ready → **ABBV** | **identified** (packet) |
| HT-027 original | insufficient | not_identified |
| HT-027 named (Clario+Solventum) | ready → **TMO** | **identified** (packet) |
| HT-009 original | insufficient | not_identified |
| HT-009 named (Pfizer/Prevnar/Paxlovid) | ready → **PFE** | **identified** (packet) |

**3/7 identified** via `historical_source_packet`. SEC-Paket: `build_sec_packet`.

## Zehner-Batch (parallel)

`docs/examples/source-packets/batch-10/`: Manifest → `build_sec_packet_batch`
→ `evidence_batch` über 10 Fälle (20 Inputs: original+named).

Freeze `batch-10/evidence-batch-10.json`: **10/10 named identified**
(ADI, CRM, MU, UNH, VRT, PFE, AVGO, DHR, ABBV, CARR); Original weiter 0/10.

## US-Rest-Batch

`batch-us-rest/`: **7/7 named identified** (KKR, JPM, JNJ, SLB, SNPS, CEG, TMO).
Zusammen mit batch-10: **17/17** US-SEC named. Same-day EDGAR filings excluded
(PIT). Gates unverändert.

## Blind 202/26 — SEC 6-K (FPI) developmental

`docs/examples/source-packets/blind-202-26-sec6k/`: Deutsche Bank 6-K exhibit
(2026-10-28) + SAN/UBS/JPM/ING/HSBC. Named (Deutsche Bank + DWS) → **identified**
via `historical_source_packet`. Original clue summary → not_identified.
Prospective freeze SHA `3fff83e1…` untouched.

## EU-SEC Batch (FPI with EDGAR)

`batch-eu-sec/`: **3/3 named identified** (SAP, BP, Eni/E).

`batch-eu-ir-wayback/`: **4/4 named identified** (ZURN, HO, LDO, ADS) via Wayback
IR lead + SEC peers (`archived_snapshot`).

`batch-pending-pdf/`: **2/2 named identified** (COST, BAS) with **PDF Stand Uhr**
cutoffs after operator upload of 192/26 & 137/26 (2026-10-31). Shared
`reference-27-inputs-with-publication-at.json` filled. **HT-016** still blocked
(no issue/date).

## Corpus-v1 (vereinigt)

`corpus-v1/`: **26/26 named identified** via `historical_source_packet`
(alle Batches außer HT-016). Original-Teaser weiter **0/26**. Freeze
`evidence-batch-corpus-v1.json`. Scorecard:
`python3 -m scanner.hebeltrader.detective.corpus_report`.

`ht-016-blocked/`: Williams SEC scaffold (WMB + peers, Transco / Northwest
Pipeline needles). **Dev only** — no issue/date, not in the freeze. Unlock
requires operator issue binding + Call-PDF Stand Uhr.

Costco/BASF cutoffs promoted (`publisher_pdf_stand_uhr`). PIT history pad
default is **800** days (`market_screen export-pit --history-pad-days`).

## Operator CLI (corpus-v1)

```bash
python3 -m scanner.hebeltrader.detective.corpus_report report
python3 -m scanner.hebeltrader.detective.corpus_report recipe
python3 -m scanner.hebeltrader.detective.corpus_report originals
python3 -m scanner.hebeltrader.detective.corpus_report tiebreak
python3 -m scanner.hebeltrader.detective.corpus_report readiness
```

Replay one corpus case through the primary CLI (named packet → Stufe 3a):

```bash
python3 -m scanner.hebeltrader.detective.investigate_cli analyze \
  --corpus-case HT-001 --corpus-variant named --root /tmp/ht-corpus-case
```

pad800 market tie-break: Top1/3/8 = **2/3/7** (unchanged vs remap); only **7/26**
named packet leaders appear in market Top-8. Charts do not replace packets.

## Stufe 3b (simuliert, offline)

Live falsification without Tavily/OpenAI:

```bash
python3 -c "from pathlib import Path; from scanner.hebeltrader.detective.simulated_falsification import run_simulated_live_falsification as r; print(r(Path('/tmp/sim3b'))['identification'])"
```

Returns `basis=live_falsification`.

## Stufe 3b (live, mit Keys)

Requires `TAVILY_API_KEY` / `DETECTIVE_SEARCH_API_KEY` (and optionally OpenAI) plus
explicit cost approval. Do **not** pass a source packet — packets force the offline path.

```bash
python3 -m scanner.hebeltrader.detective.live_falsification \
  --approve-cost --text-file teaser.txt --root /tmp/ht-live-3b
```

Tavily `GET /usage` uses a 60s client timeout (the endpoint is slower than search).

## Korpus-Grenze

27er-Original-Teaser: **0** mit ≥2 nativen Named-Ankern. Stufe 3a braucht entweder
reichere Teaser oder bewusste Diagnose-Anreicherung (wie Batch-10 named).

Blind 202/26 Chart-Scores unangetastet (Freeze SHA unverändert; DBK Rang ~565).
