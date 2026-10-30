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

## 4. Offen (nächste Schritte)
**A. Auflösung 202/26** nach Report-Kauf: Position der Lösung dokumentieren, ohne Nachziehen.

**B. Abnahme** neuer PR (Active-Call-Ausschluss); Suite grün.

### Active-Call-Ausschluss (neu)
`featured_calls.json` + `blocked_features(as_of)`: unterlyings aus früheren HEBELTRADER-Calls
innerhalb **180 Tagen** vor `publication_date` werden aus Offline-/Market-Hypothesen entfernt
(Annahme: kein Zweit-Call solange der alte läuft). Scan liest **nicht** `teaser-cases.json`.
Blind 202/26 PIT+Exclude: ADI/SNPS raus; Market-Top u. a. LLY, HNR1, IBE, KOG, LMT, MA, NXPI, NOVN.

Diagnose-Notizen: `docs/examples/reference-27-pit-diagnosis-notes-2026-10-30.md`.
Japan-Lücken: bewusst akzeptiert (`accepted_snapshot_gaps`).
