# Historisches HEBELTRADER-Backtesting V1

Issue #4 / PR #5. **Status: erledigt** (PR #5, erweitert durch V1.2+). GitHub-Issue kann geschlossen werden. Methode: `hebel-stock-ohlc-v1.2`.
Die bestehende PDF-/PostgreSQL-Architektur bleibt erhalten. V1 liefert eine
Offline-Engine mit Provider-Schnittstelle und ausschließlich lesender CLI.
Keine Migration, Outcome-Persistierung, Scheduler, Marktdaten-Abos oder Trades.
Archivordner `all`, `half`, `fail` und PDF-Dateinamen werden nicht abgefragt,
nicht gruppiert und niemals als Ground Truth verwendet.

V1.2 ergänzt einen ausdrücklich gewählten [Forschungsmodus](hebeltrader-backtest-v12.md).
Die folgenden strengen Availability-Anforderungen gelten weiterhin für den
Standardmodus `verified`; `research` dokumentiert getrennte Modellannahmen.

## Datenmodell und Ablauf

`hebel_documents` liefert Original-SHA, Publikation, Availability-Beleg, Review
und gespeicherten Originaltext. `hebel_recommendations` liefert Instrumente,
zitierte Kurse und belegte Ziele/Stopps. `hebel_publications.selected_sha`
kennzeichnet die manuell ausgewählte Originalrevision. Die Datenbank bleibt
unverändert; `hebel_outcomes` wird nicht beschrieben. Es entstehen keine neuen
Tabellen. SQLAlchemy verwendet `no_autoflush`, PostgreSQL `SET TRANSACTION READ
ONLY`; eine Sitzung wird ohne Commit geschlossen.

`backtest_provider.py` definiert `HistoricalStockProvider` und den
`CsvStockProvider`; `backtest.py` simuliert ohne Datenbank; `backtest_report.py`
prüft Quellen/Regeln und erstellt den Auditbericht. `backtest_cli.py` schreibt
JSON oder CSV. Der frühere direkte CLI-Modulaufruf bleibt kompatibel.

Jede gespeicherte Empfehlung erhält eine Zeile, auch bei fehlenden Angaben.
Ohne belegte timezone-aware `verified_available_at` plus Quellennachweis wird
`unknown / unverified_availability` ausgegeben. Eine pauschale Annahme des
nächsten Kalendertags wird hier bewusst nicht als Ausführungsbeleg verwendet.
Vor Veröffentlichung liegende Availability sowie zukünftige Availability
werden ausgeschlossen. Abgelehnte/ersetzte Dokumente und ungeklärte Revisionen
bleiben ausgeschlossen. Eine freigegebene ausgewählte Revision mit eigenem
Availability-Beleg bleibt auch bei historischem Konfliktflag nutzbar.

Pending-Dokumente mit Availability dürfen für Forschung modelliert werden;
`source_verified` verlangt zusätzlich approved, ausgewählte Revision und gültige
Availability. **`training_eligible` bleibt immer false**: diese CLI macht aus
OHLC-Modellen keine verifizierten Trainingslabels. Auch `source_verified`
bestätigt weder Kurslizenzen noch tatsächliche Ausführungen.

## Lokaler Aufruf

Abhängigkeiten/DB-Konfiguration gemäß [Hauptdokumentation](hebeltrader.md).
Nur bestehende, passend berechtigte Datenbank verwenden; keine Datenbank für
einen Backtest zurücksetzen oder neu importieren.

```bash
python -m scanner.hebeltrader backtest --help
python -m scanner.hebeltrader backtest \
  --bars-dir /sicherer/pfad/ohlcv --map /sicherer/pfad/mapping.json \
  --rules /sicherer/pfad/rules.json --as-of 2026-10-22T00:00:00+02:00 \
  --output /sicherer/pfad/berichte/backtest-20261022.json
# Für CSV einen neuen Dateinamen mit Endung .csv angeben.
```

`--rules` darf fehlen: dann bleiben Empfehlungen ohne dokumentierte Regeln
unknown. Ein Mapping `{}` ist zulässig, es erfindet keine Daten. `--as-of`
muss einen Zeitzonenoffset haben und darf nicht in der Zukunft liegen.
JSON/CSV werden nur neu mit Modus 0600 angelegt; vorhandene Dateien und
Symlinks werden nicht überschrieben. Code 0 bedeutet gültiger Bericht, auch
wenn alle Ergebnisse unknown sind; Code 2 bedeutet Aufruf-/Konfigurations-/
Ausgabefehler. Fehlerhafte einzelne Datenquellen werden im Bericht kategorisiert.
Fehlermeldungen zeigen keine SQL-Bindparameter oder Zugangsdaten.

## Kursdaten und Mapping

Die [Quellen-/Kostenentscheidung](hebeltrader-backtest-sources.md) bewertet
Yahoo/yfinance, Alpha Vantage und EODHD anhand offizieller Dokumentation.
Aktiviert ist ausschließlich lokal bereitgestelltes, entsprechend lizenziertes
CSV: Kosten der Softwareintegration EUR 0. Für alle 118 Empfehlungen wurden
weder echte historische OHLCV noch Derivat-Bid/Ask-Serien beschafft. Eine
Coverage- oder Erfolgsquote dieses tatsächlichen Bestands ist daher unbekannt.

Das [synthetische Mapping](examples/hebel-backtest/mapping.json) zeigt alle
Pflichtfelder. JSON-Schlüssel sind ausdrücklich zugeordnete Aktien-WKN oder
ISIN. Pro Zuordnung:

- `wkn` und/oder `isin`, `symbol`, `venue`, `timezone`, `currency`;
  `identity_reference`, `identity_valid_from`, `identity_valid_until` belegen die
  historische Zuordnung während des gesamten Prüfzeitraums. Keine
  Unternehmensnamen-Heuristik oder Beschränkung auf heute gelistete Aktien.
- `file`, `source_reference`, `license`, `retrieved_at`,
  `coverage_start`, `coverage_end`, `adjustment: "raw"`.
- `calendar_file`, `calendar_reference`, `corporate_actions_file`,
  `corporate_actions_reference`. Optional `delisted_at`.

Alle drei Dateien müssen unter `--bars-dir` liegen. Pfadausbruch und
Symlinks auf fremde Pfade werden verworfen. Metadatenzeiten brauchen einen
Offset; `timezone` ist eine IANA-Zone. CSV-Zeitstempel müssen den lokalen
Börsenoffset dieser Zone enthalten (einschließlich Sommerzeit).

```csv
# OHLCV (ohne diese Kommentarzeile)
timestamp,end_timestamp,open,high,low,close,volume
2026-01-02T09:30:00+01:00,2026-01-02T17:30:00+01:00,10,11,9,10,100
```

Kalender: `timestamp,end_timestamp`, genau eine vollständige Session pro Bar.
Er enthält alle echten Handelssitzungen einschließlich Sonderhandelstagen;
Feiertage werden nicht als Lücken erfunden. Actions: `timestamp,type`; ein
leerer Bestand benötigt mindestens die Headerzeile und eine Quellenreferenz.
Typen können split, dividend, currency_change, merger usw. sein: jede Action
im Prüfzeitraum führt zunächst zu `corporate_action_requires_reconciliation`.
Es erfolgt keine stille Split-/Dividendenanpassung. Bereits adjustierte Preise
werden abgelehnt, da die Originalziele auf derselben Preisbasis liegen müssen.

Die Abdeckung muss mindestens vom Publikationstag 00:00 Europe/Berlin bis zum
Stichtag reichen, einschließlich verspäteter Verfügbarkeit. Actions ab diesem
Publikationsanker werden berücksichtigt. **Stammen zitierte Preise aus einem
früheren Zeitraum, muss die Preisbasis zusätzlich manuell abgeglichen werden**;
der Publikationsanker beweist keine ältere Quote-Kompatibilität. Derzeit wird
kein kompliziertes Freitext-Quote-Datum geraten. Kalender-/Action-Vollständigkeit
und historische Identität bleiben überprüfbare Lieferantenbehauptungen,
keine vom Dateiformat selbst garantierten Fakten.

Fehlende Sessions, Duplikate, ungültige/NaN/Infinity-Kurse, negative Volumina,
unpassende Währung, Kalender-/Offsetfehler, unzureichende Identitäts-/Zeitabdeckung
oder Delisting ohne Exitbelege ergeben unknown statt Erfolg/Misserfolg.
Zukünftige und am Stichtag noch offene Bars fließen nicht ein. Retrieval muss
mindestens den Stichtag erreichen und darf nicht nach dem Berichtslauf liegen.

## Regeln aus dem damaligen Original

Ein [Regel-Sidecar](examples/hebel-backtest/rules.json) ordnet jede Interpretation
an `DOKUMENT_SHA:ORDINAL` zu, ausdrücklich nicht an einen Ordner/Dateinamen.
Er benötigt dieselbe SHA, Ordinal, `partial_fraction: "0.5"`,
`after_target1: "unchanged" | "entry" | "stop2"`, Prüfer und `reviewed_at`.
Zu jedem Regelbereich steht unter `evidence` eine Seite, ein wortgetreues Zitat
und `fields` (z.B. `partial_fraction`, `after_target1`, `exit_after`). Das Zitat
muss im gespeicherten Originaltext stehen; SHA-Prüfung schützt die Originalbytes.
`stop2` erfordert zusätzlich belegten zweiten Aktien-Stopp.

Optional: `exit_after: {"days": 20, "unit": "trading_sessions"}` oder
`calendar_days`, aber nur mit gesondert belegtem `exit_after`-Zitat. Es gibt
keine globale 20-Tage-Regel. „unchanged“ ist ebenfalls eine ausdrücklich
manuell geprüfte Interpretation und keine Vorgabe für alle PDFs.
Zitate belegen Herkunft, keine automatische semantische Interpretation:
Prüfer müssen Instrument, Teilverkauf, Regelgeltung und Zahlen aus dem damaligen
Original **ohne Kenntnis des späteren Kursverlaufs** bestätigen. Unklare Regeln
werden nicht durch automatisches NLP geraten; `missing_documented_rules` oder
`unverified_rule_evidence` bleibt die sichere Ausgabe.

## Simulation und Ergebnisbedeutung

Nur der erste vollständige Session-Open **streng nach** Availability wird als
hypothetischer Einstieg verwendet. Bei Availability während einer Session wird
kein bereits bekannter Tages-Open als handelbar angenommen. Die zitierte
Aktiennotierung steht separat in `published_stock_quote`. Derivativeinstieg,
Kursziele oder Omega werden nie aus Aktien-OHLC in Derivatperformance übersetzt.

Bei Ziel 1 werden modelliert 50% verkauft. Der Folgestopp kommt aus der
belegten Regel; die andere Hälfte kann Ziel 2, Stopp oder expliziten Zeitablauf
erreichen. Gaps verwenden den beobachteten Open, bevor Intrabar-Extreme
betrachtet werden. Nach Ziel 1 am Open wird der neue Stopp sofort berücksichtigt.
Bei unbekannter Intrabar-Reihenfolge (auch Ziel 1 gegenüber neuem Stopp) wird
`ambiguous` mit `ambiguous_intrabar`-Ereignis, Zeitintervall und ohne Rendite
ausgegeben. Ein Bar-Zeitstempel behauptet keinen exakten Intrabar-Fill.

Handelstage zählen ab Einstiegssitzung als Tag 1. Kalenderfrist: Einstieg-Open
plus N Tage; Exit am Close der letzten Sitzung mit Open bis zur Frist, erst
wenn abgeschlossene Abdeckung bis zur Frist vorliegt. Das ist eine explizite
Modellkonvention für dieses Regelprofil, keine universelle Broker-Ausführung.
Bei anders lautender PDF-Regel dieses Profil nicht als passend freigeben.
Ohne nachweisbare Frist bleibt ein offener Pfad offen. Derivat-Fälligkeit
löst keinen Aktien-Exit aus; Open-End bleibt Open-End-Metadatum.

Resultatklassen: `target1_first`, `target2_after_target1`, `stop_first`,
`expired`, `not_triggered`, `ambiguous`, `unknown`. `target1_first` kann eine
offene Restposition oder einen späteren Stopp bedeuten: `exit_reason`,
`reason` und Ereignispfad unterscheiden beides. `not_triggered` bedeutet nur,
dass im vollständigen Beobachtungsfenster kein Exit erreicht wurde.

`modeled_return_pct` ist ausschließlich die abgeschlossene **hypothetische
Bruttorendite** der modellierten Exitanteile. Spread, Gebühren und Slippage sind
unbekannt und werden explizit als solche gespeichert; keine angenommene Null.
`realized_return_pct` und `success_rate` bleiben immer null. Auch ein
ausgewähltes approved-PDF macht Tages-OHLC nicht zum Handelsausführungsbeleg.
Ohne echte zeitgestempelte Derivat-Bid/Ask bleiben Derivate immer
`derivative_unverified`, unabhängig von Aktienzielen oder Fälligkeit.

## Berichte, Audit und Reproduzierbarkeit

JSON enthält alle Empfehlungen, Klassen-/Fehlgrundzahlen und Feld-Coverage:
Anzahl vollständiger Marktdatenpfade und separat verifizierte Originalquellen.
Keine Gruppierung nach Archivordnern. Pro Empfehlung: DB-ID, SHA/Ordinal,
Publikation/Availability und Beleg, Reviewstatus, Instrument/Börse,
Quellennachweis und Retrieval-Zeit, Datei-/Mapping-/Regel-/Inputhashes,
Methodenversion, Beobachtungsfenster, Lücken, Modellannahmen und Ereignispfad.
CSV enthält die selben komplexen Auditinhalte als JSON-Zellen. Null echte
Ausführungsbelege bedeutet auch bei vollständiger Modellabdeckung keine
Erfolgsquote. Neu importierte IDs können sich zwischen Datenbanken unterscheiden;
SHA + Ordinal sind die portable Quellenidentität.

[Synthetischer JSON-Bericht](examples/hebel-backtest/report.json),
[CSV-Bericht](examples/hebel-backtest/report.csv) und alle dazugehörigen
Beispielinputs enthalten ausdrücklich erfundene Daten. Beispiel: Einstieg 10,
50%-Exit 12, Gap-Exit 9 ergeben modelliert 5% brutto; keine echte Empfehlung.
Die Source-PDF ist ebenfalls synthetisch, die dortigen Regeln Englisch-Testtext.
Reproduktion ohne Netzwerk, ohne konfigurierte DB und ohne Produktivzugriff:

```bash
python -m pip install -r requirements-dev.lock
PYTHONPATH=.:tests/hebeltrader python tests/hebeltrader/generate_backtest_example.py \
  --output-dir /tmp/neues-synthetisches-backtest-beispiel
python -m pytest -q
# Nur eine wegwerfbare PostgreSQL-Testdatenbank angeben:
TEST_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/TESTDB' python -m pytest -q
ruff check .
ruff format --check .
```

Tests decken 118 Zeilen ohne implizite Labels, unveränderte Reviews/Outcomes,
READ-ONLY auf PostgreSQL, CLI/CSV/JSON, Preis-/Regel-/Quellenfehler, Gaps,
Intrabar-Reihenfolge, Teilverkauf, Zeitregeln, Splits, Währungswechsel,
Feiertage, fehlende Sessions, Delisting, Open End und As-of-Grenzen ab.
Die PostgreSQL-Migrationssuite arbeitet destruktiv nur in der Testdatenbank.

## Geplanter Rollout / Migration (nicht ausgeführt)

1. PR prüfen; echte Quellen-, Identitäts-, Lizenz-, Kalender- und Regelbelege
   beschaffen und Abdeckung der 118 Originale einzeln prüfen. Kein Abo aktivieren.
2. Keine neue Schema-Migration erforderlich. Datenbank nicht zurücksetzen,
   Outcomes/Empfehlungen/Reviews nicht ersetzen. Bestehendes Backupverfahren
   bleibt Voraussetzung für spätere getrennte Betriebsänderungen.
3. Nach eigenständiger Betreiberfreigabe nur das Scanner-Image bauen und einen
   temporären Analyseprozess im vorhandenen getrennten Scanner-Projekt starten;
   kein API-/Worker-/Immich-Neustart nötig. Beispiel für später, nicht ausgeführt:

```bash
docker compose build pdf-import
docker compose --profile analysis run --rm --no-deps \
  -v /srv/scanner/backtest-input:/market:ro pdf-import \
  python -m scanner.hebeltrader backtest --bars-dir /market \
  --map /market/mapping.json --rules /market/rules.json \
  --as-of 2026-10-22T00:00:00+02:00 --output /reports/neuer-backtest.json
```

`--no-deps` verhindert implizite Migrationen/Service-Starts. Eingabeordner und
Berichtsrechte für UID 10001 gemäß bestehender PDF-Dokumentation vorbereiten.
Ein eigens eingeschränkter Lesebenutzer kann vom Betreiber bereitgestellt
werden; Zugangsdaten gehören außerhalb Git. Die CLI erzwingt zusätzlich die
PostgreSQL-Lesetransaktion. Es gibt keinen Persistierungs-/Trade-Schalter.
Rollback: temporären Prozess beenden und vorheriges Image verwenden;
kein DB-Downgrade nötig. Keine Docker-Kommandos auf Hetzner wurden ausgeführt.

## Prüfergebnisse dieser Änderung

22.10.2026: **165 Tests erfolgreich**, einschließlich PostgreSQL 17.6 in einer
separaten wegwerfbaren lokalen Testdatenbank. Ruff lint/format,
`git diff --check` und beide Compose-Konfigurationsprüfungen erfolgreich.
Unabhängiges Code-Review: keine verbleibenden blockierenden Befunde.
Die Prüfung umfasst keine echten Betriebsrenditen und keinen Produktivzugriff.
Docker-Build, Migrations-Smokecheck im wegwerfbaren Container und Backtest-CLI-
Hilfe im Image erfolgreich. Alle synthetischen Beispielartefakte wurden mit
dem Generator bytegleich reproduziert.
