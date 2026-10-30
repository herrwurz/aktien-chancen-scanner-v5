# Hebeltrader-Scanner: Arbeitsstand und Folgeauftrag (2026-10-30)

## 1. Ziel
Aus anonymen HEBELTRADER-Teasern die gemeinte Aktie finden. Sie soll mit sehr hoher
Wahrscheinlichkeit unter den Top 3 stehen. Der Nutzer kauft nur stichprobenartig einen Report
(ca. 10 EUR) zum Vergleich. Eine belastbare Quote liefern nur prospektive Blindtests.

## 2. Bisher erledigt (Branch `fix/chart-weighting`)
- **Referenzsammlung:** `data/hebeltrader/teaser-cases.json` hat 27 Fälle. Lösungen stehen nur
  dort und werden erst nach dem Einfrieren des Rankings gelesen.
  - HT-019 und HT-016: Lösung unbekannt (`unresolved`).
  - HT-020: `not_identified`.
  - HT-021 bis HT-027: `not_tested`.
  - Die historische 10/7/1-Bilanz gilt nur für `reference_number` 1–18.
- **Validierung:** `reference_cases.py` akzeptiert beliebige Fallzahlen, wenn die Nummern
  eindeutig sind und 1–18 vollständig vorliegen. Neue Outcomes: `not_tested`, `not_identified`.
- **Offline-Runner:** `reference_scan.py` exportiert nur
  `{case_id, headline, teaser_text, publication_date, publication_at}`. Leakage-Schranke:
  `run_scan` lehnt alle anderen Felder ab. Ergebnis über alle 27 Fälle: 27 Abstentionen,
  0 Kandidaten (keine Quellenpakete vorhanden).
- **Offline-Hypothesen** (`offline_hypotheses`): bis zu 8 Vorschläge aus `structure_screen.screen()`
  (lokales Sektor-Universum), unbelegt und getrennt von `candidates`.
  - Ergebnis: 25 Fälle mit bekannter Lösung, 17 mit Vorschlägen, Lösung in 6 enthalten
    (2× Rang 1, 4× Top 3, 6× Top 8).
  - Das ist **Entwicklungsdiagnostik**, keine unabhängige Quote, weil die Heuristik teils an
    diesen Fällen entwickelt wurde.
  - Archiv: `docs/hebeltrader-reference-proposals-2026-10-30-{rankings,evaluation}.json`
    (Ranking-SHA-256 `2ca665081c7adff5cab72a6ee4e276cb139043092dbefc9f4d6395a8d77d593c`).
- **Klare Lücken:** Zurich, Analog Devices, Salesforce, Danaher, KKR, Broadcom, Thales, BASF,
  Carrier, Adidas und AbbVie haben keinen Vorschlag. Pfizer, UNH, J&J, Vertiv, BP, Constellation
  und Eni bekommen nur falsche Vorschläge.
- **Marktdaten-Screen (neu, nur offline getestet):** `scanner/hebeltrader/detective/market_screen.py`
  und `tests/hebeltrader/test_market_screen.py` (3 Tests).
  - Der Screen liest Chart-Hinweise aus dem Teaser: 200-Tage-Linie, Ausbruch, Korrektur,
    langjähriger Aufwärtstrend.
  - Er bewertet Universumswerte anhand von Kurs-Snapshots (`export_snapshots`, `rank`).
  - Der Sektorfilter greift nur, wenn der Teaser eine Branche nennt.
- Tests: `PYTHONPATH=. pytest -q tests/hebeltrader` war zuletzt grün (493 bestanden, 8 übersprungen,
  vor dem Marktdaten-Screen). Der Marktdaten-Screen hat 3 neue Tests, die einzeln bestanden.

## 3. Blindtest 202/26 (offen)
Teaser vom 30.10.2026 „Vom Tief zum Triumph: Die Comeback-Story des Jahres!“ Branchenriese,
3. Rekordgewinn in Folge, starke Kapitalbasis, Dividenden und Rückkäufe, 200-Tage-Linie
zurückerobert, bis 1.311 %.
- Lösung unbekannt, also ein echter prospektiver Blindtest.
- Der Offline-Scan lieferte `not_identified` und keine Vorschläge, weil kein Branchenwort vorkommt.
- Meine Vermutung „Finanzwert“ ist **nicht verifiziert** und darf nicht in die Logik einfließen.
- Noch nicht eingefroren und nicht gespeichert.

## 4. Umgebung und Grenzen
- Die Sandbox hat **kein ausgehendes Internet** (DNS scheitert). EODHD, Tavily und KI sind hier nicht nutzbar.
  Die Gültigkeit des EODHD-Tokens ist unverifiziert.
- Eine lokale `.env` mit dem Token wurde angelegt. Sie ist in `.gitignore` eingetragen und **nicht committet**.
  Der Token stand im Chat und sollte danach rotiert werden.
- Nur 34 von 115 Universumswerten haben einen Ticker. Der Kursabruf nutzt die US-Börse. Nicht-US-Titel
  brauchen Börsensuffixe (z. B. `SAP.XETRA`).
- Eine Kalibrierung an den 25 Fällen ist noch nicht möglich. Es fehlen historische Kurse zum
  jeweiligen Veröffentlichungsdatum.
- „Sehr hohe Wahrscheinlichkeit Top 3“ ist mit den heutigen Daten **nicht belegt**.

## 5. Folgeauftrag (exakt)
**A. Snapshot erzeugen (Umgebung mit Internet, Token in `.env`):**
```
set -a; . ./.env; set +a
PYTHONPATH=. python -m scanner.hebeltrader.detective.market_screen export snapshots-2026-10-30.json
```
Die Datei enthält `as_of`, `exported_at` und `snapshots` pro Ticker. Prüfen: Anzahl Snapshots (Ziel ≥ 30)
und ob alle Ticker Daten liefern.

**B. Universum erweitern (ohne Overfitting):** Ticker mit Börsensuffix für Nicht-US-Werte ergänzen.
Neue Sektoren oder Werte nur nach allgemeinen, vorab dokumentierten Kriterien (z. B. Indexmitglieder
S&P 500, Stoxx 600, DAX), **nicht** anhand der bekannten Lösungen.

**C. 202/26 als Blindtest:**
1. Teaser unverändert speichern (Case-ID `BLIND-202-26`, Datum 2026-10-30, `publication_at` unbekannt).
2. `market_screen.rank(text, snapshots)` ausführen und das Ranking mit SHA-256 einfrieren, **bevor**
   die Lösung bekannt ist.
3. Logik danach nicht mehr auf diesen Fall zuschneiden.
4. Nach der Auflösung (gekaufter Report) die Position der Lösung im Ranking auswerten
   und das Ergebnis dokumentieren.

**D. Kalibrierung (nur wenn historische Kurse verfügbar):** Pro Referenzfall Kurse bis zum
Veröffentlichungsdatum holen (nie danach), Ranking einfrieren, erst dann die Lösung vergleichen.
Die Metrik ist Top-1, Top-3 und Top-8 über alle Fälle, getrennt von Entwicklungsfällen.

**E. Abnahme:** Tests grün (`PYTHONPATH=. pytest -q tests/hebeltrader`), keine Lösungsfelder im
Scan-Input, Doku aktualisiert, Token nie committen und rotieren.
