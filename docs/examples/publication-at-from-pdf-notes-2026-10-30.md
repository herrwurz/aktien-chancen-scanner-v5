# publication_at aus Publisher-PDFs (2026-10-30)

Inputs:

- `reference-27-inputs-with-publication-at.json` (24/27)
- `blind-202-26-inputs-with-publication-at.json`

`publication_at` = Guess aus PDF-`Stand: … um … Uhr` (meist 08:15 Europe/Berlin).

Pool-PIT-Diagnose mit diesen Inputs: Market-Top-8 **identisch** zur Dedup-Diagnose
(`reference-27-diagnosis-pool-pit-dedup` / Blind-Dedup) — erwartet, weil PIT weiter über
`publication_date` bucketet. Die Uhrzeit schaltet erst **Quellenpakete** frei.

Publisher-PDFs bleiben Resolutionsartefakte, keine Identifikationspakete
(`docs/hebeltrader-pdf-resolution-index.md`).
