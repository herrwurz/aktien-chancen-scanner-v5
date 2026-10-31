# Hebeltrader-Scanner: Arbeitsstand und Folgeauftrag (2026-10-30, fortgeschrieben)

## 1. Ziel
Aus anonymen HEBELTRADER-Teasern die gemeinte Aktie finden. Sie soll mit sehr hoher
Wahrscheinlichkeit unter den Top 3 stehen. Der Nutzer kauft nur stichprobenartig einen Report
(ca. 10 EUR) zum Vergleich. Eine belastbare Quote liefern nur prospektive Blindtests.

## 2. Review-Ergebnis (Copilot-`main`)
Siehe [Code-Review](hebeltrader-code-review-2026-10-30.md). Kurz: Suite grün, Evidenz-Scanner
ohne Quellenpakete bei 0 Identifikationen, Universum hatte nur 34/115 Ticker, Blindtest 202/26
war noch nicht eingefroren.

## 3. In diesem Fortsetzungsbranch erledigt
- **Ticker-Abdeckung:** alle 115 Universumsnamen haben Listing-Ticker; EODHD-Codes für Roche
  (`RO.SW`), Renk (`R3NK.XETRA`), Prysmian (`AEU.XETRA`) korrigiert. Acht Tokyo-`.TSE`-Namen
  bleiben **bewusst** ohne Snapshots: EODHD-Token ohne Japan-Börse; Teaser treffen Japan kaum —
  **kein** ADR-/Xetra-Fallback (`ticker_policy.accepted_snapshot_gaps`). Ansys: zu kurze Historie.
- **Snapshots (global):** `market_screen export` → 106/115
  (`docs/examples/snapshots-2026-10-30.meta.json`).
- **PIT-Snapshots (Paid EOD):** `export-pit` → Coverage **106–107/115** auf allen 27
  as_of-Daten (`docs/examples/snapshots-pit-2026-10-30.meta.json`). Basis:
  `publication_date_eod`. Lücken: 8× Japan `.TSE` (bewusst), Ansys teils.
- **Blindfall PIT:** `docs/examples/blind-202-26-freeze-pit/` (SHA `3bb716e5…`).
- **27er-Referenz PIT:** `docs/examples/reference-27-freeze-pit/` (SHA `150d8562…`) +
  Evaluate (Market unverified: Top1=2, Top3=2, Top8=5 bei 26 suggestion_cases; 1 ohne
  publication_date).
- **`case_diagnose`**, **`reference_evaluate`** mit Market-Coverage; Single-as_of nach
  publication_date wird als Leakage abgelehnt.

## 4. Auflösung Blind 202/26 (2026-10-30)

**Miss – Fehlerklasse A (Universum).** Lösung: **Deutsche Bank**, Call **WB14HL**.
Nicht in den eingefrorenen Top-8; fehlt im 115er-Universum. Freeze-SHA unverändert
`3fff83e1387325ccf8c1fc47d49940c5d9385244fd00518c1ea0c4722a331b0f`.
Dokumentation: [hebeltrader-202-26-resolution.md](hebeltrader-202-26-resolution.md).
DB in `featured_calls.json` für künftige Ausschlüsse ergänzt. **Kein** Score-Retuning.

## 5. Index-Pool v1 + PIT (2026-10-30)

Merged: Index-Union SPX/NDX/DAX/MDAX/SX5E/SXXP/**ATX** (~1109 Namen). Market-Screen
defaults darauf. PIT-Pool-Export: 919/1045 Bars, Coverage 904–906 / 27 as_of
(`docs/examples/snapshots-pit-pool-v1-2026-10-30.meta.json`). DBK + ATX Spot-Checks ok.

## 6. Ticker-Remap v1 (2026-10-30)
~76 PIT-Misses auf EODHD-taugliche Codes gemappt (Nordic Share-Classes, FR/UK-Korrekturen,
IT→XETRA/US wo möglich). Datei: `index_pool_ticker_remap_v1.json`.

## 7. PIT nach Remap (2026-10-30)
Re-Export: **994/1044** Bars, Coverage **979–981** (vorher 919 / 904–906).
Meta: `docs/examples/snapshots-pit-pool-v1-remap-2026-10-30.meta.json`.

## 8. Pool-PIT Diagnose Refs/Blind (2026-10-30)
`case_diagnose` auf Remap-Pool-PIT (coverage 979–981). **Kein Score-Retuning.**

- Blind 202/26: Klasse **A** geschlossen (`DBK.XETRA` kandidierbar); Residual **B_chart_rank**
  (Score 10, Rang ~622; 112× Score 23). Freeze unverändert.
- 27er Market Top-8: 6→7 / Top3 2→3 (entwicklungsdiagnostisch). Coverage ≫ kuratiert, Treffer nur leicht ↑.
- Artefakte: `*-diagnosis-pool-pit.*`, `*-pool-pit-diagnosis-notes-2026-10-30.md`,
  `blind-202-26-pool-pit-posthoc.json`.

## 9. Evidenz-Kanal + Pool-Dedup (2026-10-30)
- **Blocker:** 27er-Refs haben **0/27** `publication_at` → historische Pakete greifen nicht.
- Vertrag + Validator: `docs/hebeltrader-source-packets.md`,
  `scanner/hebeltrader/detective/source_packets.py`, synthetisches Beispiel unter
  `docs/examples/source-packets/`.
- Market-Universum: Ticker-Dedup (SPX/NDX/Curated-Namen → eine Zeile; z. B. AMGN/COST/DB1).

## 10. Vollkorpus-Check Pool-PIT+Dedup (2026-10-30)
Alle 27 Refs + Blind auf Remap-Pool-PIT mit Dedup. Market Top8 unverändert 7/25;
Offline Top8=6. Blind: DBK Rang ~565, nicht Top-8. Artefakt:
`docs/examples/full-corpus-pool-pit-check-2026-10-30.{json,md}`.

## 11. Publisher-PDF Archiv (2026-10-30)
Operator-Upload: **131** HEBELTRADER-PDFs (2025+2026, inkl. ohne Teaser).
Lokal gitignored: `data/hebeltrader/publisher-pdfs/` + `publisher-pdf-extracts/`.
Inventar (commitbar): `docs/hebeltrader-publisher-pdf-inventory.{json,md}`.
Ingest: `scripts/ingest_publisher_pdfs.py`. PDF-Meta/SHA nur im Inventar (nicht in
`teaser-cases.json` — fester Web-Import-Hash).
- Gemappt: 24/27 Refs + Blind 202/26. Lücken: HT-003 Costco **192/26** (Upload hat Costco **70/26**),
  HT-012 BASF **137/26**, HT-016 ohne Issue.
- 92× `publication_at_guess` aus „Stand: … um … Uhr“.

## 12. publication_at aus PDFs (2026-10-30)
Scan-Inputs mit Stand-Uhr-Guess: `*-inputs-with-publication-at.json` (24/27 + Blind).
Resolutionsindex: `docs/hebeltrader-pdf-resolution-index.*` (PDF ≠ Identifikationspaket).
Market-Top-8 unverändert vs Dedup-PIT (Uhr greift erst bei echten Quellenpaketen).

## 13. Quellenpaket-Pilot HT-001 (2026-10-30)
SEC-10-Q-Paket ADI+5 Peers (`docs/examples/source-packets/pilot/`). Pipeline ok;
Evidenz trotzdem **not_identified** — Teaser ohne Eigenamen (Empower/Alif nur in Auflösung).
Market-PIT: ADI Top-1. Publisher-PDFs bleiben Resolutionsartefakte.

## 14. Corpus CLI + pad800 Tie-Break + 3b-Harness (2026-10-31)
- `corpus_report {report,recipe,originals,tiebreak}` verdrahtet corpus-v1.
- pad800 market: Top1/3/8 = 2/3/7; nur 7/26 named leaders im market Top-8;
  Blind DBK Rang 565 unverändert (`B_chart_rank`).
- `simulated_falsification` übt Stufe 3b offline (`basis=live_falsification`).

## 15. Operator-Readiness + corpus-case CLI (2026-10-31)
- `corpus_report readiness` — Blocker-Board (PDFs, HT-016, Original-Gap, API-Keys).
- `investigate_cli analyze --corpus-case HT-xxx` lädt corpus-v1 Inputs+Paket
  (historical blind) → Stufe 3a Smoke ohne manuelles Packet-Pfad-Gefummel.

## 16. Offen (nächste Schritte)
**A.** Pilot auf Fälle mit **eigenamen Spezifika im Teaser**; oder Operator-Pakete mit
  Zitat-aligned IR. PDFs 192/26 + 137/26 nachreichen; HT-016 Issue+PDF.

**B.** Charts nur als Tie-Break; kein Score-Retuning von Blind 202/26 (bestätigt).

**C.** Echte Stufe 3b sobald Tavily/OpenAI Keys da sind (Harness schon grün).

### Active-Call-Ausschluss
`featured_calls.json` + `blocked_features(as_of)`: unterlyings aus früheren HEBELTRADER-Calls
innerhalb **180 Tagen** vor `publication_date` werden aus Offline-/Market-Hypothesen entfernt
(Annahme: kein Zweit-Call solange der alte läuft). Scan liest **nicht** `teaser-cases.json`.
Blind 202/26 PIT+Exclude: ADI/SNPS raus; Market-Top waren LLY, HNR1, IBE, KOG, LMT, MA, NXPI, NOVN.

Diagnose-Notizen: `docs/examples/reference-27-pit-diagnosis-notes-2026-10-30.md`.
Japan-Lücken: bewusst akzeptiert (`accepted_snapshot_gaps`).
