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
            docs/examples/source-packets/pilot-named/HT-027.inputs.original.json \
            docs/examples/source-packets/pilot-named/HT-027.inputs.named.json \
  --source-packets /path/to/packets \
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

SEC-Paket bauen: `python3 -m scanner.hebeltrader.detective.build_sec_packet`.

## Korpus-Grenze

27er-Original-Teaser: **0** mit ≥2 nativen Named-Ankern. Stufe 3a braucht entweder
reichere Teaser oder bewusste Diagnose-Anreicherung (wie HT-027 named).

Blind 202/26 und Chart-Scores unangetastet.
