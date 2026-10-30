# Example source packets

`SYNTHETIC-EXAMPLE.json` is a **synthetic** document list for schema/validator checks.
It is not a real HEBELTRADER case and must not be used as a blind benchmark.

Real packets belong here as `{case_id}.json` only when:

1. the case input has an exact `publication_at`, and
2. documents carry operator-proven availability for historical use
   (`archived_snapshot` or `sec_edgar_filing_date` binding).

Pilots:

- `pilot/` — HT-001 SEC 10-Q (no named teaser clues)
- `pilot-named/` — HT-027 Clario enrichment vs original teaser

See `docs/hebeltrader-source-packets.md`.
