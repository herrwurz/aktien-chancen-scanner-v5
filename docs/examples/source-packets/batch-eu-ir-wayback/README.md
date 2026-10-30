# Batch EU-IR-Wayback: hybrid Wayback IR + SEC peers

EU reference cases with `publication_at` but **no SEC issuer CIK**. Lead document
is a real Wayback Machine capture (`availability_evidence.basis =
archived_snapshot`, `observed_at == source_available_at`). Peers are SEC EDGAR
filings. No guessed live IR URLs.

## Ergebnis (named)

| Case | Ticker | Named anchors | identified |
|---|---|---|---|
| HT-002 | ZURN | Zurich Insurance + Beazley | ja |
| HT-011 | HO | Thales + Exail | ja |
| HT-015 | LDO | Leonardo + Baykar / LBA | ja |
| HT-025 | ADS | Adidas + Trionda / Adizero | ja |

**4/4 named** identified via `historical_source_packet`. Original: 0/4.

## Builder notes

- Builder: `python3 -m scanner.hebeltrader.detective.build_ir_wayback_packet`
- Zurich lead is a cash-offer microsite (not classic SEC “acquisition of …” prose);
  named diagnose uses `Wachstumstreiber Beazley` so the needle confirms via the
  product-literal path on the issuer page.
- Gates unverändert: ≥2 Kernhinweise, Margin ≥35, ≥5 Peer-Emittenten.

## Befehle

```bash
python3 -m scanner.hebeltrader.detective.prepare_batch_inputs \
  --manifest docs/examples/source-packets/batch-eu-ir-wayback/manifest.json \
  --out-dir docs/examples/source-packets/batch-eu-ir-wayback

python3 -m scanner.hebeltrader.detective.evidence_batch \
  --inputs docs/examples/source-packets/batch-eu-ir-wayback/HT-*.inputs.*.json \
  --source-packets docs/examples/source-packets/batch-eu-ir-wayback/packets \
  --snapshots reports/snapshots-pit-pool-v1-remap-2026-10-30.json \
  --summary docs/examples/source-packets/batch-eu-ir-wayback/evidence-batch-eu-ir-wayback.json
```

Named-Inputs sind Entwicklungsdiagnose (nicht Blind). Call-PDFs bleiben Resolution-only.
Costco / BASF (HT-003 / HT-012 / HT-016) weiter ohne `publication_at`.
