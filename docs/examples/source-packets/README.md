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
- `pilot-ht-009/` — HT-009 Pfizer (`issuer_literal` + `product_literal` → identified)
- `batch-10/` — zehn Fälle parallel (`build_sec_packet_batch`); **10/10 named identified**
- `batch-us-rest/` — restliche US-SEC der 27er; **7/7 named** (gesamt 17/17 US)
- `blind-202-26-sec6k/` — FPI **6-K** developmental packet (DB+peers); named → identified;
  prospective Blind freeze SHA untouched
- `batch-eu-sec/` — EU/FPI with SEC listings (SAP/BP/Eni); **3/3 named identified**
- `batch-eu-ir-wayback/` — EU ohne SEC-CIK (Zurich/Thales/Leonardo/Adidas);
  Wayback-IR-Lead + SEC-Peers; **4/4 named identified**
- `batch-pending-pdf/` — Costco/BASF with **PDF Stand Uhr** `publication_at`
  (192/26 & 137/26 uploaded 2026-10-31; basis=`publisher_pdf_stand_uhr`);
  **2/2 named identified**. Shared refs updated.
- `corpus-v1/` — union freeze of the five batches above; **26/26 named identified**.
  Originals 0/26. HT-016 Williams dropped from the active register (2026-10-31).
  Scorecard: `python3 -m scanner.hebeltrader.detective.corpus_report`
- `evidence-batch-pilots-2026-10-30.json` — seven-case batch freeze (3× identified: ABBV, TMO, PFE)

Costco/BASF promotion completed (`promote_provisional_publication_at.py --apply
--apply-shared-refs`). Re-run dry-run only to confirm `already_promoted`.

Corpus CLI: `python3 -m scanner.hebeltrader.detective.corpus_report {report,recipe,originals,tiebreak}`.
Stufe 3b offline harness: `scanner.hebeltrader.detective.simulated_falsification`.

See `docs/hebeltrader-source-packets.md`, `docs/hebeltrader-path-to-ticker.md`.
