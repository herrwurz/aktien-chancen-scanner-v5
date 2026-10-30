# Quellenpaket-Pilot HT-027 (named clue / Clario)

Entwicklungsdiagnose — kein unabhängiger Blind-Benchmark. Teaser-Anreicherung mit
Eigenamen nur diagnostisch; Original-Teaser bleibt separat.

## Inhalt

| Datei | Rolle |
|---|---|
| `HT-027.json` | SEC-Paket (TMO 8-K/10-Q + Peers), Text ggf. gekürzt |
| `HT-027.meta.json` | Filing-Metadaten / Clario-Flags |
| `HT-027.inputs.original.json` | Original-Teaser + `publication_at` |
| `HT-027.inputs.named.json` | Entwicklungs-Anreicherung: „Übernahme von Clario“ |
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

| Variante | checked | TMO bestätigt | Entscheidung |
|---|---|---|---|
| original | 6 | nein (Score 0) | `ambiguous_tie` |
| named (Clario) | 6 | ja, `acquisition\|clario` (1 Kernhinweis, Score 53) | `plausible_hypothesis` |

Identifikation bleibt **`not_identified`**: Gate verlangt ≥2 spezifische Primärhinweise.
Market-Top-3 (Roche/Amgen/AZN) bleibt Chart/Sektor — kein TMO.

## Root-Cause der früheren `checked_candidates=[]`

Nicht Clue-Matching. Historische Blind-Pakete mit `basis: sec_edgar_filing_date`
wurden als `uncertain` verworfen (nur `archived_snapshot` band late retrieval).
Zusätzlich mapte Packet-`source_kind: regulator` auf Evidence-`news` statt
`regulatory`. Beides ist behoben; HT-001-Pilot-README hatte denselben Blindspot
fälschlich dem fehlenden Eigenamen zugeschrieben.

## Policy

Publisher-Call-PDFs gehören **nicht** hierher. Blind 202/26 Freeze unverändert.
