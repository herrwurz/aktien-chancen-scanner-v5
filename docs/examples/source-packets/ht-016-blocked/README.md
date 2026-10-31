# HT-016 blocked — Williams SEC scaffold (dev only)

**Not part of the identification freeze.** Corpus-v1 stays **26/26** without HT-016.

## Binding (operator 2026-10-31)

| Field | Value |
|---|---|
| Case | HT-016 |
| Headline | Dieser Branchenführer profitiert vom Stromhunger der Zukunft! |
| Text | full teaser in `HT-016.inputs.original.json` |
| `publication_issue` | **191/26** |
| `publication_date` | **2026-10-15** |
| `publication_at` | `2026-10-15T08:15:00+01:00` — **provisional** (`featured_date_plus_corpus_stand_0815_pdf_pending`) |
| Outcome | unresolved (suspected WMB / Williams Companies) |
| Status | `blocked_awaiting_pdf_stand` |

Issue + featured date are bound. Exact publisher Stand Uhr still needs the Call-PDF.
Blind / ID-freeze use of this packet remains **forbidden** until Stand is PDF-confirmed
and the packet is re-cut.

## What this directory holds

Developmental SEC scaffold so peers are ready once Stand Uhr lands:

| Role | Ticker | CIK |
|---|---|---|
| Lead | WMB | 0000107263 |
| Peer | KMI | 0001506307 |
| Peer | OKE | 0001039684 |
| Peer | EPD | 0001061219 |
| Peer | ET | 0001276187 |
| Peer | LNG | 0000003570 |

Lead needles: `Transco`, `Northwest Pipeline`, `Transmission`.

Research cutoff used for the packet rebuild:
`2026-10-15T08:15:00+01:00` (same provisional Stand). Filings after that
date (e.g. prior KMI/OKE/LNG Q3 10-Qs) are excluded.

Rebuild:

```bash
python3 -m scanner.hebeltrader.detective.build_sec_packet \
  --case-id HT-016 \
  --cutoff '2026-10-15T08:15:00+01:00' \
  --issuer 'WMB:0000107263:Williams' \
  --issuer 'KMI:0001506307:Kinder Morgan' \
  --issuer 'OKE:0001039684:ONEOK' \
  --issuer 'EPD:0001061219:Enterprise Products' \
  --issuer 'ET:0001276187:Energy Transfer' \
  --issuer 'LNG:0000003570:Cheniere' \
  --needle Transco \
  --needle 'Northwest Pipeline' \
  --needle Transmission \
  --out docs/examples/source-packets/ht-016-blocked/packets/HT-016.json \
  --raw-dir data/hebeltrader/source-packet-raw/HT-016
```

## Operator unlock (remaining)

1. Upload Call-PDF for 191/26; run `scripts/ingest_publisher_pdfs.py`.
2. Confirm `publication_at` from the PDF `Stand: … um … Uhr` line.
3. Re-cut the packet with that cutoff; only then consider corpus promotion.
4. Shared `reference-27-inputs-with-publication-at.json` stays untouched until then.

Related: `scripts/promote_provisional_publication_at.py` (Costco 192/26,
BASF 137/26). HT-016 stays blocked there until PDF Stand.
