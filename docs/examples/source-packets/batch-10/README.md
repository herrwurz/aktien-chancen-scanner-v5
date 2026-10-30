# Batch-10: zehn Fälle parallel

Ein Manifest → Pakete bauen → Evidence-Batch. Kein Einzelfall-Hopping.

## Ergebnis (named Diagnose-Anreicherung)

| Case | Ticker | Named → identified |
|---|---|---|
| HT-001 | ADI | ja (Empower-Übernahme) |
| HT-004 | CRM | ja |
| HT-005 | MU | ja |
| HT-006 | UNH | ja |
| HT-007 | VRT | ja (PurgeRite-Übernahme) |
| HT-009 | PFE | ja |
| HT-010 | AVGO | ja |
| HT-013 | DHR | ja (Masimo-Übernahme) |
| HT-023 | ABBV | ja |
| HT-026 | CARR | ja |

**10/10 named** → `historical_source_packet`. Original-Teaser: 0/10 identified (Korpus-Lücke).

## Qualitätsgates (nicht gelockert)

- ≥2 bestätigte Kernhinweise, Score-Margin ≥35, ≥5 Peer-Emittenten
- Kein Peer mit denselben harten Fact-Clues (Leakage-Audit)
- Generische Produkt-Tokens (`Data`, `Cloud`, …) werden verworfen; Multi-Word (`Data Cloud`) bleibt
- Freeze-Tests: `tests/hebeltrader/test_batch_10_quality.py`

## Befehle

```bash
python3 -m scanner.hebeltrader.detective.prepare_batch_inputs \
  --manifest docs/examples/source-packets/batch-10/manifest.json \
  --out-dir docs/examples/source-packets/batch-10

python3 -m scanner.hebeltrader.detective.build_sec_packet_batch \
  --manifest docs/examples/source-packets/batch-10/manifest.json \
  --out-dir docs/examples/source-packets/batch-10/packets \
  --workers 2

python3 -m scanner.hebeltrader.detective.evidence_batch \
  --inputs docs/examples/source-packets/batch-10/HT-*.inputs.*.json \
  --source-packets docs/examples/source-packets/batch-10/packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --summary docs/examples/source-packets/batch-10/evidence-batch-10.json
```

Named-Inputs sind Entwicklungsdiagnose (nicht Blind). Call-PDFs bleiben Resolution-only. Blind 202/26 unverändert.
