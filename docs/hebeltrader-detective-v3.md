# HEBELTRADER-Detektiv V3

Der Detektiv untersucht unbekannte Börsenteaser aus Text, PDF oder Bild. Er durchsucht den zum
Publikationszeitpunkt sichtbaren lokalen Research-Index, prüft bis zu 50 Kandidaten gegen
archivierte Evidenz und gibt höchstens drei Kandidaten aus. Der Evidenzwert ist keine
Trefferwahrscheinlichkeit und keine Kaufempfehlung.

## Datenfluss

1. Die Eingabe wird mit SHA-256 und Seitenbezug archiviert. PDF-Dateien sind auf 20 MiB und 40
   Seiten begrenzt; Textschichten werden vor OCR verwendet.
2. Der Parser trennt Aktienfakten, Derivatekennungen und Werbesprache. Angaben wie „1.091 % mit
   diesem Call“ werden nicht als Umsatz- oder Gewinnwachstum verwendet.
3. Stage A durchsucht alle historisch sichtbaren Indexwerte über getrennte Struktur- und
   Textkanäle. Die Ergebnislisten werden mit eingefrorener Reciprocal Rank Fusion verbunden.
4. Stage B kennzeichnet jeden Hinweis als `confirmed`, `contradicted` oder `unknown`. Unbekannte
   Angaben zählen neutral. Übernommene Veröffentlichungen desselben Ursprungs zählen einmal.
5. `likely_candidate` erfordert mindestens drei bestätigte Hinweise aus zwei Kategorien, zwei
   unabhängige Evidenzcluster einschließlich einer Primärquelle, keinen harten Widerspruch und 20
   Punkte Abstand. Ansonsten lautet das Ergebnis `unclear` oder `unresolved`.

Eine historische Analyse ohne belegte Publikationszeit endet mit `missing_publication_time`.
Quellen ohne nachweisbares `available_at` und später veröffentlichte Korrekturen werden nicht
verwendet. Heute abgerufene Stammdaten gelten nicht automatisch als historisch verfügbar.

## Quellenabdeckung

Der vorhandene Index kann SEC-Identität, Land, eine enge SIC-Branchenzuordnung, ausgewählte
XBRL-Werte und normalisierte Unternehmensereignisse belegen. GLEIF dient ausschließlich der
Rechtsträgeridentität. Konkrete Produkte, Kunden, Partner, freie Geschäftsbeschreibungen,
Marktstellung und historische Marktkapitalisierung bleiben ohne archivierten Primärbeleg
`unknown`. Die SEC-Basis ist keine globale Aktienabdeckung; insbesondere DACH und große Teile
Europas bleiben unvollständig.

Im Offline- und API-Startpfad gibt es keine Netzwerkanfragen. Live-Recherche bleibt explizit,
zugangsgeschützt und durch Requests sowie Laufzeit begrenzt. V3 benötigt keinen kostenpflichtigen
Dienst.

## Blindtests

Scanner und Evaluator sind getrennte Programme. Der Scanner erhält nur zufällig benannte
Eingabefälle, Index und Ausgabepfad:

```bash
python -m scanner.hebeltrader.detective.benchmark_scan \
  --inputs tests/fixtures/detective-v3/inputs/manifest.json \
  --research-index /pfad/research-index.db \
  --output /tmp/detective-v3/rankings.json
```

Erst nach beendetem Scan erhält der Evaluator die getrennte Labeldatei:

```bash
python -m scanner.hebeltrader.detective.benchmark_evaluate \
  --rankings /tmp/detective-v3/rankings.json \
  --labels tests/fixtures/detective-v3/solutions/labels.json \
  --output /tmp/detective-v3/evaluation.json
```

Die zehn mitgelieferten Fälle sind ausdrücklich synthetische Funktionstests. Sie belegen keine
reale Erkennungsrate. Weniger als zehn echte Originalfälle ergeben
`insufficient_real_benchmark_coverage`.

## Reale read-only Abnahme

Voraussetzungen sind ein unveränderter Originalteaser, seine belegte Publikationszeit, ein
dokumentierter Nutzungsstatus und ein vorhandener Research-Index. Das Skript verwendet ein
eigenes Verzeichnis, deaktiviert das Netzwerk, mountet Eingabe und Index nur lesend und verändert
weder PostgreSQL noch andere Docker-Projekte:

```bash
cd /opt/aktien-chancen-scanner-v5
mkdir -p /opt/scanner-detective-v3-output
DETECTIVE_IMAGE=scanner-detective-v3 \
  scripts/run_detective_v3_real.sh \
  /opt/private-teasers/teaser.pdf \
  2025-08-05T08:15:00+02:00 \
  authorized_local_analysis \
  /opt/scanner-research/sec-index.db \
  /opt/scanner-detective-v3-output
```

Der Lauf schreibt `preflight.json`, `preflight.csv`, `preflight.sha256`, `analysis.json` und
`analysis.sha256`. Er benötigt keinen API-Schlüssel. Die bestätigte Aktie und die unabhängige
Lösungsquelle werden erst nach dem Scan in einem getrennten Evaluationsschritt bereitgestellt.

In der Entwicklungsumgebung lag kein unveränderter realer Vorab-Teaser mit belegter separater
Lösung vor. Der reale Abnahmestatus bleibt deshalb `pending_external_material`; es werden weder
eine reale Trefferquote noch ein erfolgreicher Praxistest behauptet.

## Derivate

Die Aktienidentifikation läuft zuerst. Eine Derivate-WKN wird nur ausgewiesen, wenn sie ausdrücklich
in der Eingabe vorkommt und zeitlich gültige Produktdaten vorliegen. Ohne Emittent, Basiswert,
Produktart, ISIN/WKN, Bezugsverhältnis, Basispreis und Laufzeit bleibt sie
`unresolved_product_identifier`. Renditeangaben erzeugen niemals eine WKN.
