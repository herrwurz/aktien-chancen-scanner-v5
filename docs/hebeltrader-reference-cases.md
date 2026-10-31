# HEBELTRADER-Referenzfälle – Stand 30.10.2026

## Datenbestand und Herkunft

Die kanonische Sammlung liegt in [teaser-cases.json](../data/hebeltrader/teaser-cases.json).
Der Datensatz enthält **26 aktive Fälle**: 17 historische Nutzerrekonstruktionen
(ursprünglich 18; **HT-016 Williams am 2026-10-31 gestrichen**, `reference_number` 2
bleibt als Lücke) und neun Erweiterungen. Bestehende HT-IDs bleiben sonst stabil;
`reference_number` bezeichnet die Nummer im Nutzerauftrag. Nur Fälle 1–18 ohne die
gestrichene Nr. 2 bilden die historische 10/7-Bilanz. Erweiterte Fälle haben getrennte
Statuswerte wie `not_tested` und `not_identified`. Fehlende Angaben bleiben `null`.
Die [zentrale Wissensbasis](hebeltrader-identification-rules.md) enthält das aktive
historische Register. Ihr früherer Tabellenstand bleibt im
[Archiv](archive/hebeltrader-register-before-reference-refresh-2026-10-28.md).

Die Auflösungen sind überwiegend Nutzerangaben aus Gesprächsrekonstruktionen, keine neu
unabhängig geprüften Emittentenbelege. Call-WKNs sind Produktkennungen, keine Aktienkennungen.
Die Gesprächsbilanz der aktiven historischen Fälle lautet **10 richtig, 7 falsch,
0 ungelöst**. Die daraus berechneten 58,8 % bei 17 Auflösungen sind ausdrücklich keine
neue Scanner-Trefferquote. Frühere 55/60/95-%-Angaben sind als unkalibrierte historische
Aussagen gespeichert.

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

Zusätzlich erzeugt der Offline-Lauf aus dem anonymen Teasertext höchstens acht
`offline_hypotheses` aus dem lokalen Sektor-/Unternehmensuniversum. Diese sind unbestätigte
Suchvorschläge, keine belegten Scanner-Kandidaten; sie bleiben getrennt von `candidates`
und ändern den Identifikationsstatus nicht. Erst das eingefrorene Ranking wird mit den
Lösungen verglichen. Die Auswertung weist die Treffer dieser Vorschlagsliste separat aus
und kennzeichnet sie als Entwicklungsdiagnostik, nicht als unabhängigen Benchmark.

## Tatsächliche Prüfung

Der archivierte 18-Fälle-Lauf ist ein früherer quellenloser Regressionstest; sein
[eingefrorenes Ranking](hebeltrader-reference-rankings.json), seine
[Auswertung](hebeltrader-reference-evaluation.json) und der dort dokumentierte Hash
gehören zu genau diesem alten Lauf.

Der aktuelle lokale Hypothesen-Baseline-Lauf verarbeitet alle **26** aktiven Fälle, ohne
Referenz- oder Lösungsdaten im Scanprozess zu lesen. Für die 25 Fälle mit bekannter Lösung
enthält die unbelegte Vorschlagsliste den Zielnamen in **6 Fällen** (2 auf Vorschlag 1,
4 in den ersten 3, 6 in den ersten 8); 17 Fälle erzeugen überhaupt Vorschläge. Der
evidenzbasierte Scanner identifiziert weiterhin **0 Fälle**, da keine historischen
Quellenpakete oder exakten Veröffentlichungszeitpunkte vorliegen. Diese Zahlen sind
Entwicklungsdiagnostik, keine Scanner-Trefferquote und kein unabhängiger Benchmark.

Der Lauf ist reproduzierbar archiviert: [eingefrorene Vorschläge](hebeltrader-reference-proposals-2026-10-30-rankings.json),
[separate Auswertung](hebeltrader-reference-proposals-2026-10-30-evaluation.json);
Ranking-SHA-256: `2ca665081c7adff5cab72a6ee4e276cb139043092dbefc9f4d6395a8d77d593c`.

**0 unabhängige Blindtests.** Der frühere manuelle SLB-Fall bleibt separat dokumentiert.

Das ist eine überprüfte Entwicklungsreferenz, keine fachliche Abnahme eines zuverlässig
identifizierenden autonomen Detektivs. Fünf echte Gegenkandidaten wurden in diesem
quellenlosen Referenzlauf nicht recherchiert; es werden keine erfundenen Kandidaten ergänzt.

## Fehlende Originale und nächster Schritt

Vollständiger Originaltext liegt für **23 von 26 aktiven Fällen** vor. Er fehlt bei
HT-022 (Constellation Energy), HT-023 (AbbVie) und HT-025 (Adidas). Die
Auflösungsdaten von JPMorgan und J&J werden nicht als Teaserdaten ausgegeben. Alle
exakten Veröffentlichungszeitpunkte und alle ursprünglichen vollständigen Top-3-
Rangfolgen fehlen. Die beiden zusätzlichen damaligen JPMorgan-Gegenkandidaten bleiben
ohne erfundene Reihenfolge gespeichert. Das Thales-Datum ist ausdrücklich ungeprüft.

Für belastbare historische Identifikationsprüfungen werden rechtmäßig bereitgestellte
Originalteaser sowie zeitlich belegte Unternehmensquellen benötigt. Danach einen zuvor
ungesehenen öffentlichen Teaser mit mindestens fünf tatsächlich geprüften Kandidaten
analysieren und das erste Ranking vor jeder Auflösung einfrieren. Keine Trefferquote aus
den bekannten, zur Entwicklung verwendeten 18 Fällen ableiten.
