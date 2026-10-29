# 18 HEBELTRADER-Referenzfälle – Stand 28.10.2026

## Datenbestand und Herkunft

Die kanonische Sammlung liegt in [teaser-cases.json](../data/hebeltrader/teaser-cases.json).
Alle 18 vom Nutzer rekonstruierten Fälle sind enthalten. Bestehende HT-IDs bleiben stabil;
`reference_number` bezeichnet die Nummer im neuen Nutzerauftrag. Fehlende Angaben bleiben
`null`. Die [zentrale Wissensbasis](hebeltrader-identification-rules.md) enthält dieselben
Tabellenwerte. Ihr früherer Tabellenstand bleibt im [Archiv](archive/hebeltrader-register-before-reference-refresh-2026-10-28.md).

Die Auflösungen sind überwiegend Nutzerangaben aus Gesprächsrekonstruktionen, keine neu
unabhängig geprüften Emittentenbelege. Call-WKNs sind Produktkennungen, keine Aktienkennungen.
Die frühere Gesprächsbilanz lautet **10 richtig, 7 falsch, 1 ungelöst**. Die daraus berechneten
58,8 % bei 17 Auflösungen sind ausdrücklich keine neue Scanner-Trefferquote. Williams bleibt
ungelöst. Frühere 55/60/95-%-Angaben sind als unkalibrierte historische Aussagen gespeichert.

## Änderungen der Recherche

Suchanfragen werden aus dem anonymen Text abgeleitet: Übernahmen und die Kombination
konkreter Geschäftsfelder zuerst, danach Quartalszahlen, Marge und Free Cashflow. Beim
ADI-Teaser werden keine Namen aus der späteren Auflösung eingespeist. Empower und Alif
stehen ausschließlich in den getrennten Auflösungshinweisen. Optionsschein-WKNs und
Werberenditen dienen nicht als Suchschlüssel für den Basiswert.

Die Recherche bricht nicht mehr nach acht ungeprüften Firmennamen ab. Alle anfänglichen
Top-3-Kandidaten erhalten eine Gegenrecherche. Neu aufgerückte Kandidaten werden als noch
nicht falsifiziert markiert. Bestehende Quellenbudgets und Identifikationsschranken bleiben
wirksam. Diese Änderungen beweisen noch keine bessere Erkennungsquote; öffentliche
Suchquellen und zuverlässige weltweite Kandidatenextraktion bleiben begrenzt.

Die sieben Fehler zeigen zwei wiederkehrende Ursachen: allgemeine Branchen-/Comeback-
Formulierungen wurden übergewichtet und direkte Wettbewerber zu früh ausgeschlossen.
Beim Fall Lattice/ADI kam Bestätigungssuche hinzu. Die ursprünglichen Fehlprognosen sind
weiter gespeichert; der Evaluator ersetzt sie nicht durch heutige richtige Namen.

## Lösungstrennung und reproduzierbarer Lauf

Der Kurator exportiert ausschließlich Fall-ID, Überschrift, verfügbaren Originaltext,
Veröffentlichungsdatum und belegten Zeitpunkt. Der Scanner importiert weder Referenz-
Evaluator noch Lösungssammlung. Der separate Evaluator liest Lösungen erst nach Prüfung
des SHA-256 des eingefrorenen Rankings.

Mit installiertem Projekt-Python und lokal gebautem Docker-Image, vom Repository aus:

```bash
docker build -t teaser-references:local .
scripts/run_teaser_reference_regression.sh \
  "$PWD/data/hebeltrader/teaser-cases.json" \
  /tmp/hebeltrader-reference-run-001 teaser-references:local
python -m scanner.hebeltrader.detective.reference_evaluate \
  --rankings /tmp/hebeltrader-reference-run-001/scans/rankings.json \
  --references data/hebeltrader/teaser-cases.json \
  --output /tmp/hebeltrader-reference-run-001/evaluation.json
```

Jeder Lauf benötigt einen neuen Ausgabeordner. Das Skript mountet nur den bereinigten
Eingabeexport und einen frischen Ausgabeordner, verwendet `--network none` und ein
schreibgeschütztes Containerdateisystem. Referenzdaten, Dokumentation und PDFs werden
nicht in das Docker-Image kopiert. Der Evaluator läuft anschließend außerhalb des
Scannercontainers. Kein Serverlauf, Deployment oder zusätzlicher Datentarif ist nötig.

Für historische Quellenpakete unterstützt `reference_scan --source-packets` eine separate
Eingabe. Ohne belegten exakten Veröffentlichungszeitpunkt wird kein historischer Cutoff
erraten und kein Paket als damalige Evidenz verwendet. Die aktuelle Sammlung enthält
keine solchen Zeitpunkte; ein Datum allein wird nicht zu einer Uhrzeit umgedeutet.

## Tatsächliche Prüfung

- Vollständige lokale Testsuite: **761 bestanden, 8 PostgreSQL-Tests übersprungen**;
  eine bestehende Starlette/AnyIO-Deprecation-Warnung. Ruff erfolgreich.
- Isolierter Docker-Lauf mit allen 18 bereinigten Eingaben erfolgreich.
- Ergebnis: **18 ungelöst, 0 belegte Identifikationen**. Keine historischen Quellenpakete
  verfügbar; dies prüft Datenfluss, Einfrieren, Trennung und ehrliches Enthalten.
- [Eingefrorenes Ranking](hebeltrader-reference-rankings.json) und
  [maschinenlesbare Auswertung](hebeltrader-reference-evaluation.json) sind archiviert.
- Ranking-SHA-256: `1dcc3c5bb7ab1b240332090db39c1ad20042fa3632e3f776cc86af4f21eb7c9d`.
- **0 neue unabhängig ausgewertete Blindtests** in diesem Auftrag. Der frühere manuelle
  SLB-Fall ist separat dokumentiert und wird diesen 18 Fällen nicht zugerechnet.

Das ist eine überprüfte Entwicklungsreferenz, keine fachliche Abnahme eines zuverlässig
identifizierenden autonomen Detektivs. Fünf echte Gegenkandidaten wurden in diesem
quellenlosen Referenzlauf nicht recherchiert; es werden keine erfundenen Kandidaten ergänzt.

## Fehlende Originale und nächster Schritt

Vollständiger Originaltext liegt nur für **HT-001 / Fall 18 (ADI)** vor. Für die folgenden
17 Fälle fehlt er: Costco, Williams, Zurich, Salesforce, Micron, UnitedHealth, Vertiv,
Danaher, SAP, KKR, Pfizer, Broadcom, Leonardo, Thales, BASF, JPMorgan und Johnson & Johnson.

Das Veröffentlichungsdatum fehlt bei Williams, SAP, Pfizer, BASF, JPMorgan und J&J.
Die Auflösungsdaten von JPMorgan und J&J werden nicht als Teaserdaten ausgegeben.
Alle 18 exakten Veröffentlichungszeitpunkte und alle ursprünglichen vollständigen
Top-3-Rangfolgen fehlen. Die beiden zusätzlichen damaligen JPMorgan-Gegenkandidaten
bleiben ohne erfundene Reihenfolge gespeichert. Das Thales-Datum ist ausdrücklich ungeprüft.

Für belastbare historische Identifikationsprüfungen werden rechtmäßig bereitgestellte
Originalteaser sowie zeitlich belegte Unternehmensquellen benötigt. Danach einen zuvor
ungesehenen öffentlichen Teaser mit mindestens fünf tatsächlich geprüften Kandidaten
analysieren und das erste Ranking vor jeder Auflösung einfrieren. Keine Trefferquote aus
den bekannten, zur Entwicklung verwendeten 18 Fällen ableiten.
