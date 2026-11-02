# Batch pending-PDF: Costco / BASF (PDF Stand confirmed)

Reference gaps **HT-003** (Costco **192/26**) and **HT-012** (BASF **137/26**)
were filled by operator upload on 2026-10-31. `publication_at` is now bound to
the publisher PDF `Stand: … um … Uhr` line via
`scripts/promote_provisional_publication_at.py --apply --apply-shared-refs`.

## Confirmed cutoff

| Case | Issue | Featured date | `publication_at` | Basis |
|---|---|---|---|---|
| HT-003 | 192/26 | 2026-10-16 | `2026-10-16T08:15:00+01:00` | `publisher_pdf_stand_uhr` |
| HT-012 | 137/26 | 2026-07-31 | `2026-07-31T08:15:00+01:00` | `publisher_pdf_stand_uhr` |

PDFs (gitignored archive): `Hebeltrader_2026-192_Costco_c7dd.pdf`,
`Hebeltrader_2026-137_BASF_7a75.pdf`. Call-WKNs from ingest: Costco **JY5SQZ**,
BASF **MJ7DUX**.

Shared `reference-27-inputs-with-publication-at.json` now carries these cutoffs.

## Ergebnis (named)

| Case | Ticker | Named anchors | identified |
|---|---|---|---|
| HT-003 | COST | Costco + Kirkland | ja |
| HT-012 | BAS | BASF + Oppanol | ja |

**2/2 named** via `historical_source_packet`. Original: 0/2.

## Packets

- HT-003: SEC 10-Q Costco + WMT/TGT/BJ/DG/DLTR peers
- HT-012: Wayback IR (Oppanol N PLUS PR) + DOW/DD/LYB/EMN/CE peers

## Note

**HT-016** Williams was dropped from the active register (2026-10-31);
this batch never included it.

## Gates

Unchanged: ≥2 Kernhinweise, Margin ≥35, ≥5 Peer-Emittenten. Blind 202/26
untouched. Call-PDFs remain resolution-only (cutoff source, not packet body).
