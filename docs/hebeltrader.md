# Historische HEBELTRADER-Analyse

Das Modul ergänzt den bestehenden Scanner um lokale PDF-Extraktion und
historische Empfehlungsdaten. Es startet keine Trades, aktiviert keine Dienste
und verändert weder Immich noch den Krypto-Scheduler. Der Import ist ein
expliziter CLI-Aufruf, kein Hintergrundauftrag.

## Daten und Qualität

`pdfplumber` liest Text, Wörter mit Seitenpositionen und erkannte Tabellen. Der
HEBELTRADER-Parser erkennt Veröffentlichungsdatum und Ausgabe aus Seitenköpfen,
Derivatblöcke und zugehörige Basiswertblöcke. Aktien- und Derivat-WKN/ISIN,
Kurse, Ziele und Stopps bleiben getrennt. Auch Basispreis-Währung und
Handelswährung des Derivats sind separate Felder. Erfasst werden außerdem Produktart,
expliziter Emittent, Basispreis, Fälligkeit/Laufzeittext, Omega/Hebel samt
Originalbezeichnung, CRV und fundamentale/charttechnische Kommentare.

Ein `Akt. Kurs` ist eine **Indikation**, kein nachgewiesener Einstieg oder
Ausführungskurs. Emittenten werden nicht aus WKNs erraten. Nicht vorhandene
Angaben bleiben `NULL`. Deutsche Zahlen werden strikt geprüft; Konflikte,
ungültige Kennungen, fehlende Pflicht-/Analysefelder und abgelaufene Laufzeiten
erhalten Prüfbefunde. Auch ein erfolgreicher Import bleibt zunächst `pending`.

Jedes Feld besitzt Belege mit Seite, Bounding Box, Rohtext und Parserregel.
Nicht zuverlässig zuordenbare Abschnitte werden markiert. Gespeicherte
Seiten-/Tabellenextraktionen und Originalbytes ermöglichen die manuelle Prüfung,
auch wenn die Quelldatei später umbenannt wird. Die Qualitätsflags sind Hinweise,
keine statistisch kalibrierte Konfidenzwahrscheinlichkeit. Unklassifizierter
Eröffnungstext bleibt als `source_commentary` erhalten und wird nicht automatisch
als fundamentaler Hinweis oder Modellmerkmal ausgegeben.

Gescannten PDFs ohne Textschicht wird `ocr_required` zugeordnet. OCR ist noch
nicht eingebaut. Fehlerhafte PDFs werden mit Fehlerklasse und Prüfcode erfasst;
andere Dateien werden weiter importiert. Unbekannte Layouts sind Prüfobjekte,
keine automatisch als vollständig bestätigten Datensätze.

## Datenbank

Die additive Migration `0002` verwendet die vorhandene SQLAlchemy-Basis und
fügt ausschließlich `hebel_*`-Tabellen hinzu:

| Tabelle | Inhalt |
| --- | --- |
| `hebel_publications` | Eindeutige Ausgabe aus Jahr/Nummer, ausgewählte Dokumentversion |
| `hebel_documents` | SHA-256, Originalbytes, Publikationsdatum, Seiten, Parserversion, Prüfbefunde |
| `hebel_source_locations` | Relative Dateipfade, Wurzel-ID und unverifizierte Herkunftskategorien |
| `hebel_recommendations` | Typisierte Felder mit Decimal-Werten, Feldbelegen und Prüfmarkierungen |
| `hebel_import_runs` | Start/Ende und vollständiger Importbericht |
| `hebel_reviews` | Explizite Freigaben/Ablehnungen mit Prüfer und Begründung |
| `hebel_outcomes` | Vorbereitete, derzeit unbefüllte Ergebnisablage mit Quellen-/Methodenbezug |

Die SHA-256-Prüfsumme identifiziert exakte Originalbytes. Kopien unter anderen
Namen oder Kategorien erzeugen neue Herkunftsbezüge, keine neuen Empfehlungen.
Jahr/Ausgabenummer identifizieren die Ausgabe. Abweichende PDF-Versionen derselben
Ausgabe bleiben getrennte, nachvollziehbare Varianten innerhalb einer Ausgabe;
eine zuvor gewählte Version verliert ihre Analysefreigabe. Eine erneute manuelle
Auswahl ist erforderlich. Bei Varianten erfordert die Freigabe außerdem eine
quellspezifisch belegte Verfügbarkeitszeit. Es findet kein stilles Überschreiben statt.

Bei identischen erneuten Imports wird dieselbe Extraktion weiterverwendet.
Versioniertes Re-Parsing bereits gespeicherter Dokumente nach einer zukünftigen
Parseränderung ist noch kein CLI-Befehl; Originalbytes und Parserversion bleiben
für diese Erweiterung erhalten.

`all`, `half` und `fail` werden nur aus dem relativen Ordnerpfad übernommen.
Sie bleiben **unverifiziert**. Die Software interpretiert sie niemals als
Gewinn-, Teilgewinn- oder Verlustnachweis. Mehrere Fundorte bleiben erhalten.

## Lokaler Start

Voraussetzung: bestehende Projektumgebung mit Python 3.12 und eine konfigurierte
PostgreSQL-Verbindung über `.env` oder `DATABASE_URL` wie in der Haupt-README.
Für eine ausschließlich lokale Demo ist SQLite möglich.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
# Nur lokale Demo, keine Betriebsdatenbank:
export DATABASE_URL='sqlite:///./hebeltrader-demo.db'
alembic upgrade head
python -m scanner.hebeltrader import \
  --pdf-dir /absoluter/pfad/hebeltrader \
  --report-dir /absoluter/pfad/importberichte \
  --expected-count 118
```

Der Import sucht rekursiv und berücksichtigt auch `.PDF`. Symlinks werden nicht
als PDFs importiert. Pro PDF gelten 50 MiB und höchstens 100 Seiten. Das
Original wird zusätzlich im privaten PostgreSQL-Datenvolume gespeichert;
118 Ausgaben mit etwa 0,7 MiB beanspruchen bereits rund 83 MiB vor Indizes,
Seitenextraktionen und Backups. Das Quellverzeichnis wird nicht verändert.

Umgebungsvariablen für den lokalen CLI-Aufruf:

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `HEBELTRADER_PDF_DIR` | `data/hebeltrader` | Lokaler Quellordner |
| `HEBELTRADER_REPORT_DIR` | `reports/hebeltrader` | Privater Berichtspfad |
| `HEBELTRADER_EXPECTED_COUNT` | nicht gesetzt | Erwartete Dateianzahl; CLI-Flag hat Vorrang |

Der Bericht steht als JSON auf stdout, als `import-<UUID>.json` im Berichtspfad
und in `hebel_import_runs`. Er enthält gefundene, neu importierte, übersprungene
und fehlgeschlagene Dateien, neu angelegte Empfehlungen sowie neue Dokumente zur
Prüfung (`needs_review`). Dieser Zähler ist kein Gesamtbestand aller offenen
Prüffälle. Je Datei werden Status, Prüfsumme, Fehlerklasse und Qualitätsbefunde
ausgegeben. Existierende Berichtsdateien werden nicht überschrieben.

Exit 0: Importdurchlauf ohne Dateifehler oder Anzahlwarnung; das bedeutet **keine
inhaltliche Freigabe**. Exit 2: Fehler, leerer Ordner, nicht erfüllte erwartete
Anzahl oder ungültige Konfiguration. Ein zweiter Import derselben PDFs meldet
`skipped_duplicate`. Ein bereits als defekt erfasstes PDF bleibt als Fehler
erkennbar. Bei DB-Verbindungs-/Migrationsfehlern zuerst die Verbindung und
`alembic upgrade head` prüfen; Fehlermeldungen enthalten keine Zugangsdaten oder
SQL-Bind-Parameter.

## Manuelle Prüfung und Analyseexport

```bash
python -m scanner.hebeltrader inspect --sha SHA256_AUS_IMPORTBERICHT
python -m scanner.hebeltrader review --sha SHA256_AUS_IMPORTBERICHT \
  --action approve --reviewer 'Name des Prüfers' \
  --note 'Originalseiten geprüft; verbleibende optionale Lücken akzeptiert'
python -m scanner.hebeltrader export \
  --as-of '2026-01-01T00:00:00+01:00' \
  --output /absoluter/pfad/features-2026-01-01.json
```

Zum Ablehnen `--action reject` verwenden. Das ist auch für Dokumente ohne
sicheres Veröffentlichungsdatum möglich. Für eine Freigabe müssen Datum,
Ausgabenidentität und mindestens eine belegte Empfehlung vorliegen. Die
Freigabe akzeptiert ausdrücklich verbleibende Lücken; sie füllt keine Werte auf
und entfernt keine ursprünglichen Prüfbefunde. Ein Datum darf nicht aus
Dateiname, Upload- oder Importzeit ergänzt werden. Konflikte müssen am Original
geprüft werden; unbelegbare Daten bleiben ausgeschlossen. Der CLI bietet keine
stille Feldkorrektur oder automatische Freigabe aller Dateien.

Nur freigegebene und ausdrücklich ausgewählte Dokumentversionen gehen in den
Export ein. Ohne bekannte Veröffentlichungsuhrzeit wird als **gekennzeichnete
Annahme** das Ende des Publikationstags in `Europe/Berlin` angesetzt. Erst ab
Mitternacht des Folgetags, korrekt nach UTC umgerechnet, darf der Datensatz im
zeitbezogenen Export erscheinen. Die Uhrzeit einer Kursindikation wird nicht
als Veröffentlichungszeit übernommen.

Bei Variantenkonflikten reicht eine allgemeine Freigabe nicht aus:

```bash
python -m scanner.hebeltrader review --sha SHA256_DER_GEPRUEFTEN_VERSION \
  --action approve --reviewer 'Prüfer' --note 'Archivfassung geprüft' \
  --available-at '2025-03-01T09:00:00+01:00' \
  --availability-evidence 'Nachweis der Archivfassung mit eindeutigem Versionsbezug'
```

Zeitpunkt und Beleg werden am Dokument und im Review-Protokoll gespeichert.
Der Export verwendet diesen Zeitpunkt statt des ursprünglichen Ausgabetags.
Varianten ohne solchen Nachweis bleiben ausgeschlossen. Ein Zeitpunkt vor dem
Publikationstag oder ohne Zeitzone wird abgewiesen.

Die Funktion rekonstruiert publizierte Angaben anhand heute vorliegender Quellen;
sie beweist nicht, dass eine später geladene oder überarbeitete PDF damals
bereits genau so verfügbar war. Gerade bei Dokumentvarianten muss der Prüfer
die historische Version nachweisen. `as_of` bedeutet historische fachliche
Verfügbarkeit unter dieser Annahme, nicht damalige lokale Import-/Kenntniszeit.

Der explizite Feature-Katalog enthält keine Ordnerkategorien, späteren Outcomes,
Importzeiten, unklassifizierte Kommentare oder Freigabestatus. Quellenhash, Ausgabe, Publikationsdatum und
Annahme stehen außerhalb von `features`. Ein Train-/Test-Split muss später
chronologisch auf Ausgabenebene erfolgen; Kategorien und spätere Ergebnisse
dürfen nicht als Modellmerkmale verwendet werden.

Erfolgsquoten oder Renditen werden noch nicht berechnet. Dafür fehlen separat
belegte Kursreihen, Handelskalender, Derivatpreise, Kosten und eindeutige
Ausführungsregeln. Besonders Ziel und Stopp innerhalb derselben Tageskerze,
Teilverkauf und spätere Stoppanpassungen dürfen nicht rückblickend zugunsten
eines Ergebnisses aufgelöst werden. `hebel_outcomes` bleibt beim Import leer.

## Docker und Hetzner-Vorbereitung

Der optionale Service `pdf-import` gehört zum bestehenden Compose-Projekt und
ist ausschließlich im Profil `analysis` aktiv. Er nutzt das bestehende Image
und private Backend-Netzwerk, öffnet keine Ports und hat kein Egress-Netzwerk.
Das Quellverzeichnis ist read-only, der Berichtspfad separat beschreibbar.
Ein normales `docker compose up` startet den Import nicht.

In `.env` die existierenden Host-Verzeichnisse konfigurieren:

```dotenv
HEBELTRADER_PDF_DIR=/srv/scanner/hebeltrader-pdfs
HEBELTRADER_REPORT_DIR=/srv/scanner/hebeltrader-reports
HEBELTRADER_EXPECTED_COUNT=118
```

Der Containerbenutzer UID/GID 10001 benötigt Leserechte auf die Quelle und
Schreibrechte auf den Berichtspfad. Beispielsweise nur für neu angelegte
Scanner-Verzeichnisse vorbereiten:

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /srv/scanner/hebeltrader-reports
# Nach Bereitstellung der PDFs, falls ACL-Werkzeuge vorhanden:
sudo setfacl -Rm u:10001:rX /srv/scanner/hebeltrader-pdfs
```

Vor einer späteren Migration Betriebsdaten sichern, wie in der Haupt-README
beschrieben. Folgende Befehle sind dokumentierte Schritte für den Betreiber;
es erfolgt durch diesen Pull Request kein Deployment:

```bash
docker compose --profile analysis config --quiet
docker compose build pdf-import
docker compose up -d db
docker compose run --rm migrate
docker compose --profile analysis run --rm --no-deps pdf-import
# Wiederholungsimport: derselbe Befehl; keine Duplikate.
docker compose --profile analysis run --rm --no-deps pdf-import \
  python -m scanner.hebeltrader inspect --sha SHA256_AUS_IMPORTBERICHT
```

Andere CLI-Kommandos können entsprechend als abweichender Service-Befehl
aufgerufen werden. Exportpfade im Container unter `/reports` wählen. Bei
kleineren Testbeständen `import --expected-count ANZAHL` explizit angeben.
Scanner-API und Markt-Worker müssen für den Import nicht neu gestartet werden.
Es werden keine Immich-Container, externen Netzwerke oder fremden Volumes
benötigt. Globales Docker-Pruning gehört nicht zu diesen Schritten.

## Google Drive

Die Anwendung hat bewusst keinen anonymen oder automatisch autorisierten
Drive-Download. Ein zuvor autorisiert exportierter lokaler Ordner oder ein
sicher konfigurierter, ausschließlich lesender Drive-Mount dient als Eingabe.
Zugriff nur für die benötigten Dateien, Token/Service-Account-Konfiguration
außerhalb des Repositorys und außerhalb des Image-Build-Kontexts verwalten.
Auf Hetzner vorhandene Drive-Zugänge müssen ausdrücklich vom Betreiber
bereitgestellt werden; eine Chat-Connector-Autorisierung wird nicht auf den
Server übertragen. Keine öffentlichen Freigabelinks erforderlich.

Im Entwicklungsprozess wurde eine Originalausgabe über den bereits autorisierten
Drive-Connector lokal geprüft. Sie ist kein Repository-Testfixture. In Git
stehen nur erfundene PDF-Beispiele; Originaldaten und Berichte bleiben privat.

## Tests und Grenzen

```bash
python -m pytest -q
ruff check .
ruff format --check .
# Ausschließlich wegwerfbare PostgreSQL-Testdatenbank angeben:
TEST_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/TESTDB' python -m pytest -q
```

Die PostgreSQL-Tests führen absichtlich Migrationen, Downgrades und TRUNCATE aus;
niemals gegen Betriebsdaten ausführen. Synthetische Beispiele decken beide
Instrumente, mehrere Empfehlungen, Tabellen, Lücken, Konflikte, Kopien,
Metadatenfehler, Scan-/defekte PDFs, Freigaben und zeitbezogene Exporte ab.
Die Migration wird auch auf Erhalt vorhandener Scanner-Daten geprüft.

Der Parser ist eine nachvollziehbare erste Layoutimplementierung, keine
garantierte Vollerkennung aller 118 Ausgaben. Ein vollständiger Bestandsimport
mit anschließender manueller Qualitätsprüfung bleibt ein eigener Lauf beim
Betreiber. Tatsächlich ausgeführte Prüfungen: [hebeltrader-test-results.md](hebeltrader-test-results.md).

## Parser V2.1

Diagnose, geprüfter Vergleich aller 118 Originale und der ausschließlich lesende
`quality`-Befehl: [hebeltrader-v21.md](hebeltrader-v21.md). Bestehende Importe und
manuell geprüfte Daten werden durch einen Wiederholungsimport nicht neu geparst.
