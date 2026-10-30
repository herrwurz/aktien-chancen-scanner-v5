# Quellenpaket-Pilot HT-001 (SEC 10-Q)

Entwicklungsdiagnose — kein unabhängiger Blind-Benchmark.

## Inhalt

| Datei | Rolle |
|---|---|
| `HT-001.json` | 6 SEC-10-Q-Dokumente (ADI + TXN/NXPI/MCHP/ON/AVGO), Text ggf. gekürzt |
| `HT-001.meta.json` | Filing-Metadaten / Empower-Alif-Flags |
| `HT-001.inputs.json` | Scan-Inputs inkl. `publication_at` |
| `HT-001.scan-summary.json` | Ergebnis der Offline-Untersuchung |

Roh-HTML (vollständig): `data/hebeltrader/source-packet-raw/HT-001/` (**gitignored**).

## Lauf

```bash
python3 -m scanner.hebeltrader.detective.reference_scan \
  --inputs docs/examples/source-packets/pilot/HT-001.inputs.json \
  --source-packets docs/examples/source-packets/pilot \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --root /tmp/ht001-packet-scan
```

## Ergebnis (kurz)

- Pakete geladen (`source_packet_status=provided`), 6 Firmenidentitäten.
- Evidenz-Identifikation: **`not_identified` / `insufficient_specific_primary_evidence`**.
- Ursache: Teaser nennt keine eindeutigen Eigenamen (Empower/Alif nur in der Auflösung);
  Matcher findet keine spezifischen Primärtreffer gegen die 10-Qs.
- Market-Kanal (Pool-PIT): **ADI Top-1** (Score 17) — Chart/Sektor, keine Identifikation.

## Policy

Publisher-Call-PDFs gehören **nicht** in diesen Ordner. Nur Regulatorik/IR mit
`published_at` vor Cutoff und `availability_evidence`.
