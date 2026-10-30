# Quellenpaket-Pilot HT-027 (named clue / Clario + Solventum)

Entwicklungsdiagnose — kein unabhängiger Blind-Benchmark. Teaser-Anreicherung mit
Eigenamen nur diagnostisch; Original-Teaser bleibt separat.

## Inhalt

| Datei | Rolle |
|---|---|
| `HT-027.json` | SEC-Paket (TMO 8-K/10-Q inkl. Acquisition-Prosa + Peers) |
| `HT-027.meta.json` | Filing-Metadaten / Clario-/Solventum-Flags |
| `HT-027.inputs.original.json` | Original-Teaser + `publication_at` |
| `HT-027.inputs.named.json` | Entwicklungs-Anreicherung: Clario **und** Solventum |
| `HT-027.summary.*.json` | Offline-Scan-Ergebnisse |

Roh-HTML: `data/hebeltrader/source-packet-raw/HT-027/` (**gitignored**).

## Lauf

```bash
python3 -m scanner.hebeltrader.detective.reference_scan \
  --inputs docs/examples/source-packets/pilot-named/HT-027.inputs.named.json \
  --source-packets data/hebeltrader/source-packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --root /tmp/ht027-named-scan
```

## Ergebnis (kurz)

| Variante | checked | TMO | `packet_evidence` | `identification` |
|---|---|---|---|---|
| original | 6 | Score 0 | `insufficient_evidence` | not_identified |
| named (Clario+Solventum) | 6 | 2 Kernhinweise, Score 105 | **`ticker_hypothesis_ready` → TMO** | **`identified`** (`historical_source_packet`) |

Bestätigte Quotes: **Clario**, **Solventum**. Historisches Paket mit ≥5 Peer-Emittenten
reicht für Offline-`identified`; Live-Falsifikation bleibt der Web-Pfad.

Market-Top-3 (Roche/Amgen/AZN) bleibt Chart/Sektor — kein TMO.

## Matcher-Lektionen

1. `sec_edgar_filing_date` muss late retrieval binden (sonst `checked=[]`).
2. Packet-`regulator` → Evidence-`regulatory`.
3. SEC-Prosa: `the company acquired … from Target` braucht Issuer-Anaphora.
4. Naive 80k-Kürzung verwirft Acquisition-Notes — Prosa-Fenster behalten.
5. `Gewinnsprung von mehr als 40 %` ist jetzt ein `financial_metric` (hier ohne
   Primärbestätigung im 10-Q).

## Policy

Publisher-Call-PDFs gehören **nicht** hierher. Blind 202/26 Freeze unverändert.
