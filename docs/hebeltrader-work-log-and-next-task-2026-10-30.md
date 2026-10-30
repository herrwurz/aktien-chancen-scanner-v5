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
  bleiben Snapshot-Lücken (Japan-EOD auf dem aktiven Plan nicht verfügbar). Ansys: zu kurze
  Historie (Übernahme).
- **Snapshots:** Live-Export `market_screen export` → 106/115 Features
  (`docs/examples/snapshots-2026-10-30.meta.json`; Rohdatei unter gitignore
  `reports/hebeltrader/snapshots-2026-10-30.json`).
- **Blindfall mit Charts:** `docs/examples/blind-202-26-freeze-snapshots/`
  (SHA `6a777229…`); Clue `above_gd200`; Market-Top unverified; weiterhin `not_identified`.
- **27er-Referenz mit Charts:** `docs/examples/reference-27-freeze-snapshots/` + Diagnose +
  Evaluate (`market_hypothesis_coverage`: Top1=1, Top3=2, Top8=5 bei 25 graded — unverified).
- **`case_diagnose`:** lösungsfreie Ausgabe Hinweise/Coverage/Top-8 (JSON+Markdown).
- **`reference_evaluate`:** `market_hypothesis_rank` / `market_hypothesis_coverage`.

## 4. Offen (nächste Schritte)
**A. Japan-EOD** erst nach Plan mit TSE-Zugang oder bewusster ADR-/Xetra-Fallback-Politik.

**B. PIT-Kalibrierung** nur mit Kursen ≤ Veröffentlichungsdatum der Referenzfälle
(`--as-of` je Fall, nicht Global-as-of).

**C. Auflösung 202/26** nach Report-Kauf: Position der Lösung in structure-/market-Hypothesen
dokumentieren, ohne Logik auf diesen Fall zuzuschneiden.

**D. Abnahme:** `PYTHONPATH=. pytest -q tests/hebeltrader` grün; keine Lösungsfelder im Scan-Input;
Token nur als Cursor-Secret / `.env`, nie committen.
