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
- **PIT-Snapshots:** `export-pit` → `by_as_of` je `publication_date`
  (`docs/examples/snapshots-pit-2026-10-30.meta.json`). Basis: letzter Close ≤ Datum
  (`publication_date_eod`). Aktuelles Token liefert ~1 Jahr Historie → vor ~2026-08-20 oft
  `insufficient_history_at_as_of` (GD200 braucht ≥200 Sessions). Für volle PIT-Tiefe:
  **EOD Historical All-World**.
- **Blindfall PIT:** `docs/examples/blind-202-26-freeze-pit/` (SHA `ba738555…`).
- **27er-Referenz PIT:** `docs/examples/reference-27-freeze-pit/` + Evaluate
  (Market unverified: Top1=3, Top3=3, Top8=6 bei 16 suggestion_cases; 10 insufficient history,
  1 ohne publication_date).
- **`case_diagnose`**, **`reference_evaluate`** mit Market-Coverage; Single-as_of nach
  publication_date wird als Leakage abgelehnt.

## 4. Offen (nächste Schritte)
**A. EOD-Historie** auf All-World (30+ Jahre) prüfen/upgraden, dann PIT-Export + Freeze für
May–Jul-2026-Fälle wiederholen.

**B. Auflösung 202/26** nach Report-Kauf: Position der Lösung dokumentieren, ohne Nachziehen.

**C. Abnahme:** Suite grün; Token nur Secret/`.env`.

Japan-Lücken: bewusst akzeptiert (`accepted_snapshot_gaps`).
