# Example source packets

`SYNTHETIC-EXAMPLE.json` is a **synthetic** document list for schema/validator checks.
It is not a real HEBELTRADER case and must not be used as a blind benchmark.

Real packets belong here as `{case_id}.json` only when:

1. the case input has an exact `publication_at`, and
2. documents carry operator-proven availability for historical use
   (`archived_snapshot` or `sec_edgar_filing_date` binding).

Pilots:

- `pilot/` — HT-001 SEC 10-Q (no named teaser clues)
- `pilot-named/` — HT-027 Clario+Solventum → **identified** via historical packet
- `pilot-original-anchors/` — corpus gap + HT-023 AbbVie (`issuer_literal` + `product_literal` → identified)
- `evidence-batch-pilots-2026-10-30.json` — five-case batch freeze (2× identified: ABBV, TMO)

See `docs/hebeltrader-source-packets.md`, `docs/hebeltrader-path-to-ticker.md`.
