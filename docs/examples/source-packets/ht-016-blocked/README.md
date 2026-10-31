# HT-016 blocked — Williams SEC scaffold (dev only)

**Not part of the identification freeze.** Corpus-v1 stays **26/26** without HT-016.

## Why blocked

| Field | Value |
|---|---|
| Case | HT-016 |
| Headline | Dieser Branchenführer profitiert vom Stromhunger der Zukunft! |
| Text | headline-only (`teaser_text=null`) |
| `publication_issue` | null |
| `publication_date` / `publication_at` | null |
| Outcome | unresolved (suspected WMB / Williams Companies) |

Without an operator-bound issue + Stand Uhr there is no historical cutoff.
Blind / ID-freeze use of this packet is **forbidden**.

## What this directory holds

Developmental SEC scaffold so the day a real `publication_at` lands we do not
rebuild peers from scratch:

| Role | Ticker | CIK |
|---|---|---|
| Lead | WMB | 0000107263 |
| Peer | KMI | 0001506307 |
| Peer | OKE | 0001039684 |
| Peer | EPD | 0001061219 |
| Peer | ET | 0001276187 |
| Peer | LNG | 0000003570 |

Lead needles (product / system literals): `Transco`, `Northwest Pipeline`,
`Transmission`. Research as-of used for the fetch:
`2026-10-30T08:15:00+01:00` — **provisional research cutoff only**, not a
publisher Stand.

Lead filing in the scaffold: WMB 10-Q filed 2026-08-03
(`sec_edgar_filing_date`). Rebuild:

```bash
python3 -m scanner.hebeltrader.detective.build_sec_packet \
  --case-id HT-016 \
  --cutoff '2026-10-30T08:15:00+01:00' \
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

## Operator unlock

1. Bind HT-016 to a Hebeltrader issue (or confirm it stays unresolved).
2. Upload the matching Call-PDF; run `scripts/ingest_publisher_pdfs.py`.
3. Set real `publication_at` from the PDF `Stand: … um … Uhr` line.
4. Re-cut the packet with that cutoff; only then consider corpus promotion.
5. Shared `reference-27-inputs-with-publication-at.json` stays untouched until
   then.

Related: `scripts/promote_provisional_publication_at.py` (Costco 192/26,
BASF 137/26). HT-016 is listed there as still blocked.
