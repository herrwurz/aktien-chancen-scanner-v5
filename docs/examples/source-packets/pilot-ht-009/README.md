# Quellenpaket-Pilot HT-009 (Pfizer / product_literal)

Entwicklungsdiagnose — kein Blind-Benchmark. Call-PDF bleibt Resolutionsleak.

## Ergebnis

| Inputs | `packet_evidence` | `identification` |
|---|---|---|
| original (Comeback-Teaser, nur Kennzahlen) | insufficient | not_identified |
| named (Konzern Pfizer + Prevnar/Paxlovid) | ready → **PFE** (3 Hinweise, Score 156) | **identified** (`historical_source_packet`) |

## Paket

SEC EDGAR vor Cutoff `2026-08-11T08:15:00+01:00`:

- Lead: Pfizer 10-Q/8-K (Fokusfenster auf Umsatz-Prosa Prevnar/Paxlovid/Eliquis/Comirnaty)
- Peers: JNJ, MRK, ABBV, LLY, AMGN, BMY

Roh-HTML: `data/hebeltrader/source-packet-raw/HT-009/` (**gitignored**).

## Dateien

| Datei | Rolle |
|---|---|
| `HT-009.json` | SEC-Paket |
| `HT-009.meta.json` | Filing-Metadaten / Produkt-Flags |
| `HT-009.inputs.original.json` | Original-Teaser + `publication_at` |
| `HT-009.inputs.named.json` | Diagnose-Anreicherung: Konzern + Produkte |
| `HT-009.summary.*.json` | Offline-Scan-Ergebnisse |

## Bauen

```bash
python3 -m scanner.hebeltrader.detective.build_sec_packet \
  --case-id HT-009 \
  --cutoff '2026-08-11T08:15:00+01:00' \
  --issuer 'PFE:0000078003:Pfizer:extra8k' \
  --issuer 'JNJ:0000200406:Johnson & Johnson' \
  --issuer 'MRK:0000310158:Merck' \
  --issuer 'ABBV:0001551152:AbbVie' \
  --issuer 'LLY:0000059478:Eli Lilly' \
  --issuer 'AMGN:0000318154:Amgen' \
  --issuer 'BMY:0000014272:Bristol-Myers Squibb' \
  --needle Prevnar --needle Paxlovid --needle Eliquis --needle Comirnaty \
  --out docs/examples/source-packets/pilot-ht-009/HT-009.json \
  --raw-dir data/hebeltrader/source-packet-raw/HT-009
```

Blind 202/26 unverändert.
