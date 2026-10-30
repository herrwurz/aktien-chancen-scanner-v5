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

`batch-eu-sec/`: **3/3 named identified** (SAP, BP, Eni/E). Zurich / Thales /
Leonardo / Adidas have no SEC issuer CIK — deferred. Costco / BASF still lack
`publication_at`.

## Korpus-Grenze

27er-Original-Teaser: **0** mit ≥2 nativen Named-Ankern. Stufe 3a braucht entweder
reichere Teaser oder bewusste Diagnose-Anreicherung (wie Batch-10 named).

Blind 202/26 Chart-Scores unangetastet (Freeze SHA unverändert).
