# Hebeltrader-Scanner: Arbeitsstand und Folgeauftrag (2026-10-30, fortgeschrieben)

## 1. Ziel
Aus anonymen HEBELTRADER-Teasern die gemeinte Aktie finden. Sie soll mit sehr hoher
Wahrscheinlichkeit unter den Top 3 stehen. Der Nutzer kauft nur stichprobenartig einen Report
(ca. 10 EUR) zum Vergleich. Eine belastbare Quote liefern nur prospektive Blindtests.

## 2. Review-Ergebnis (Copilot-`main`)
Siehe [Code-Review](hebeltrader-code-review-2026-10-30.md). Kurz: Suite grün (498+ Tests),
Evidenz-Scanner ohne Quellenpakete bei 0 Identifikationen, Universum hatte nur 34/115 Ticker,
Blindtest 202/26 war noch nicht eingefroren.

## 3. In diesem Fortsetzungsbranch erledigt
- **Ticker-Abdeckung:** alle 115 Universumsnamen haben Primärlisting-Ticker (EODHD-Suffixe für
  Nicht-US). Kriterien dokumentiert in `global_universe.json` (`ticker_policy`); keine
  lösungsgetriebenen Namens-Erweiterungen.
- **Blindfall:** [`docs/examples/blind-202-26-inputs.json`](examples/blind-202-26-inputs.json)
  + eingefrorenes Ranking unter `docs/examples/blind-202-26-freeze/` und Meta
  [`hebeltrader-blind-202-26-freeze.json`](hebeltrader-blind-202-26-freeze.json)
  (SHA in der Datei). Lösung unbekannt; nach Auflösung nicht nachkalibrieren.
- **`reference_scan --snapshots`:** optional Chart-Hypothesen aus `market_screen`-Export;
  bleibt von `candidates` und Identifikationsstatus getrennt.
- Ohne Snapshots: Blindfall weiter `not_identified`, 0 Sektor-Hypothesen (kein Branchenwort).

## 4. Offen (nächste Schritte)
**A. Snapshots mit EODHD** (Umgebung mit Token in `.env`, Token nie committen, rotieren):
```
set -a; . ./.env; set +a
PYTHONPATH=. python -m scanner.hebeltrader.detective.market_screen export \
  reports/hebeltrader/snapshots-2026-10-30.json
```
Ziel: ≥100 Snapshots bei 115 Tickern. Danach Blindfall und 27er-Referenz mit
`--snapshots` erneut einfrieren (neuer Output-Ordner).

**B. Kalibrierung** nur mit Kursen ≤ Veröffentlichungsdatum der Referenzfälle.

**C. Auflösung 202/26** nach Report-Kauf: Position der Lösung in structure-/market-Hypothesen
dokumentieren, ohne Logik auf diesen Fall zuzuschneiden.

**D. Abnahme:** `PYTHONPATH=. pytest -q tests/hebeltrader` grün; keine Lösungsfelder im Scan-Input.
