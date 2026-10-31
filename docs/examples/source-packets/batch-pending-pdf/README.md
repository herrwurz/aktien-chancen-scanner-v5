# Batch pending-PDF: Costco / BASF (provisional cutoff)

Reference gaps **HT-003** (Costco **192/26**) and **HT-012** (BASF **137/26**)
still lack the publisher Call-PDFs in the upload set. Without the PDF
`Stand: … um … Uhr` line we do **not** mutate
`reference-27-inputs-with-publication-at.json`.

## Provisional cutoff (developmental only)

| Case | Issue | Featured date | Provisional `publication_at` |
|---|---|---|---|
| HT-003 | 192/26 | 2026-10-16 | `2026-10-16T08:15:00+01:00` |
| HT-012 | 137/26 | 2026-07-31 | `2026-07-31T08:15:00+01:00` |

Basis: `featured_date` from `featured_calls.json` + corpus-canonical Stand
**08:15** (all 92 PDF `publication_at_guess` values in the inventory use 08:15).
Flag: `publication_at_basis=featured_date_plus_corpus_stand_0815_pdf_pending`.

**Operator unblock:** upload `Hebeltrader_2026-192_*Costco*.pdf` and
`Hebeltrader_2026-137_*BASF*.pdf`, re-run `scripts/ingest_publisher_pdfs.py`,
then replace provisional cutoffs with PDF Stand guesses in the shared refs.

## Ergebnis (named, provisional cutoff)

| Case | Ticker | Named anchors | identified |
|---|---|---|---|
| HT-003 | COST | Costco + Kirkland | ja |
| HT-012 | BAS | BASF + Oppanol | ja |

**2/2 named** via `historical_source_packet`. Original: 0/2.

## Packets

- HT-003: SEC 10-Q Costco + WMT/TGT/BJ/DG/DLTR peers
- HT-012: Wayback IR (Oppanol N PLUS PR) + DOW/DD/LYB/EMN/CE peers  
  (BASF has no SEC issuer CIK)

## Still blocked

**HT-016** — no `publication_issue`, no featured date, identity unresolved
(Williams family). Needs operator issue binding before any packet.

## Gates

Unchanged: ≥2 Kernhinweise, Margin ≥35, ≥5 Peer-Emittenten. Blind 202/26
untouched. Call-PDFs remain resolution-only.
