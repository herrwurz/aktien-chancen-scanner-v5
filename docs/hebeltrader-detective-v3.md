# HEBELTRADER-Detektiv V3

## Falllebenszyklus in der Weboberfläche

Gespeicherte Testfälle werden nicht physisch gelöscht. **Archivieren** hängt ein signiertes
Journalereignis an, blendet den Fall aus der aktiven Liste aus und schließt ihn aus
Qualitätskennzahlen aus. Über „Archivierte Fälle anzeigen“ bleibt er prüfbar.

Ein neuer Teaser kann nach eingefrorener Erstprognose und vor Kenntnis der Lösung als
prospektiver Blindtest markiert werden. Erst nach einer belegten späteren Auflösung darf er als
prospektiver Referenzfall freigegeben werden. Die 18 rekonstruierten Entwicklungsreferenzen
bleiben davon getrennt; gekaufte PDFs bleiben im privaten persistenten Speicher.

Der Detektiv untersucht unbekannte Börsenteaser aus Text, PDF oder Bild. Er durchsucht den zum
Publikationszeitpunkt sichtbaren lokalen Research-Index bzw. ein kuratiertes EU/DACH-Universum,
prüft bis zu 50 Kandidaten gegen archivierte Evidenz und gibt höchstens drei Kandidaten aus. Der
Evidenzwert ist keine Trefferwahrscheinlichkeit und keine Kaufempfehlung.

Standardmodus ist `analysis_mode=hypothesis`: brauchbare Top-3-Hypothesen mit Gründen
(`hypothesis_top3`), manuell zu prüfen. `analysis_mode=strict` behält die hohe
`likely_candidate`-Schwelle. Clue-Enrichment erzeugt Suchqueries (heuristisch, optional per
`DETECTIVE_LLM_ENDPOINT`). Promo-Renditen bleiben außerhalb der Fundamentalbewertung.

## Datenfluss

1. Die Eingabe wird mit SHA-256 und Seitenbezug archiviert. PDF-Dateien sind auf 20 MiB und 40
   Seiten begrenzt; Textschichten werden vor OCR verwendet.
2. Der Parser trennt Aktienfakten, Derivatekennungen und Werbesprache. Angaben wie „1.091 % mit
   diesem Call“, „1.717 Prozent Rendite“ oder „1.717 % Potenzial“ werden nicht als Umsatz- oder
   Gewinnwachstum verwendet.
3. Stage A durchsucht alle historisch sichtbaren Indexwerte über getrennte Struktur- und
   Textkanäle. Die Ergebnislisten werden mit eingefrorener Reciprocal Rank Fusion verbunden.
4. Stage B kennzeichnet jeden Hinweis als `confirmed`, `contradicted` oder `unknown`. Unbekannte
   Angaben zählen neutral. Übernommene Veröffentlichungen desselben Ursprungs zählen einmal. Der
   Evidenzscore bewertet nur bestätigte Hinweise, Kategorienbreite und unabhängige Cluster; harte
   Widersprüche sortieren einen Kandidaten hinter alle widerspruchsfreien Treffer. Stage-A-RRF dient
   nur als Gleichstandskriterium, nicht als Ersatz für Fakten.
5. `likely_candidate` erfordert mindestens drei bestätigte Hinweise aus zwei Kategorien, zwei
   unabhängige Evidenzcluster einschließlich einer Primärquelle, keinen harten Widerspruch und 20
   Punkte Abstand zum besten widerspruchsfreien Zweitplatzierten. Ansonsten lautet das Ergebnis
   `unclear` oder `unresolved`.

Im strengen Modus endet eine Analyse ohne belegte Publikationszeit mit
`missing_publication_time`. Im Hypothesenmodus wird ohne Zeitstempel die Analysezeit genutzt
(nicht `historical_blind`). Quellen ohne nachweisbares `available_at` und später veröffentlichte
Korrekturen werden nicht verwendet. Heute abgerufene Stammdaten gelten nicht automatisch als
historisch verfügbar.

DACH/EU-Stammdaten fließen über das kuratierte Seed-Universum und optional OpenFIGI-Identitäten
(`DETECTIVE_OPENFIGI_IDENTITIES`) in Stage A; `build_index_with_eu_universe` schreibt sie in den
Research-Index. News-Queries aus dem Clue-Enrichment speisen den Fixture-/GDELT-News-Kanal.

`unresolved` trägt einen konkreten `failure_code`, soweit belegbar:

- `insufficiently_constrained` – keine belastbare Stage-A-Einschränkung;
- `not_in_universe` – ausdrückliche Aktienkennung fehlt im sichtbaren Universum oder das
  sichtbare Universum ist leer;
- `retrieval_missed` – Universum vorhanden, aber kein Kandidat in Stage A;
- `evidence_missing` – Kandidaten vorhanden, aber ohne ausreichende bestätigte Evidenz;
- `all_candidates_contradicted` – alle Kandidaten haben harte Widersprüche.

Die Coverage-Antwort enthält `full_universe_size`, `visible_universe_size`,
`matched_before_limit`, `channel_limit` (50), Treffer je Kanal vor und nach dem Cutoff sowie
`stage_a_asset_ids`.

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

Scanner und Evaluator sind getrennte Programme. Für Blindläufe startet das Skript einen
netzwerklosen, schreibgeschützten Container, in den nur Eingaben, Index samt Integritätsmanifest
und Ausgabe gemountet werden. Der Lösungsordner ist im Scannerprozess nicht vorhanden:

```bash
scripts/run_detective_v3_blind_scan.sh \
  tests/fixtures/detective-v3/inputs/manifest.json \
  /pfad/research-index.db \
  /tmp/detective-v3/rankings.json \
  scanner-detective-v3
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
dokumentierter Nutzungsstatus und ein vorhandener Research-Index einschließlich der benachbarten
Datei `<index>.manifest.json`. Zulässige `rights_status`-Werte:
`authorized_local_analysis`, `rights_holder_permission`,
`public_domain_or_license_cleared`. Die Gold-Lösung bleibt bis nach dem Scan ungemountet. Fehlt
Material, schreibt der Preflight `pending_external_material` mit `blockers` und `next_steps`; das
Real-Skript bricht dann ab, bevor eine Analyse als Erfolg wirkt.

Das Skript verwendet ein
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
Für die Nachprüfung sind mindestens Top-3, `failure_code`, Primärbelege, Unbekanntes und die
Artifact-SHAs festzuhalten.

In der Entwicklungsumgebung lag kein unveränderter realer Vorab-Teaser mit belegter separater
Lösung vor. Der reale Abnahmestatus bleibt deshalb `pending_external_material`; es werden weder
eine reale Trefferquote noch ein erfolgreicher Praxistest behauptet.

## Derivate

Die Aktienidentifikation läuft zuerst. Eine Derivate-WKN wird nur ausgewiesen, wenn sie ausdrücklich
in der Eingabe vorkommt und zeitlich gültige Produktdaten vorliegen. Ohne Emittent, Basiswert,
Produktart, ISIN/WKN, Bezugsverhältnis, Basispreis und Laufzeit bleibt sie
`unresolved_product_identifier`. Renditeangaben erzeugen niemals eine WKN.
