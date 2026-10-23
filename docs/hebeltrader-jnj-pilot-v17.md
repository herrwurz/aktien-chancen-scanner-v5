# V1.7: Johnson & Johnson als echter, schreibgeschützter Pilot

V1.7 ergänzt die vorhandenen V1.5-EODHD- und V1.6-Modellmodule. Es gibt keine
Migration, Änderung von Originaldatensätzen, automatische Freigabe oder Orders.
Der Pilot ist ein Offline-Bericht; Datensammlung erfolgt separat und nur nach
ausdrücklicher Freigabe. Auf Hetzner wurden hier keine Befehle ausgeführt.

## Tatsächlich erreicht

Der lokale Originaldatensatz wurde über SHA
`0223ed07b672b4f02379cff6477d24290de3801d89179a0fa4c0e9c2a44268fc`, Ordinal 1,
eindeutig geladen und mit dem Auftrag abgeglichen. Publikation: 05.08.2025,
WKN 853260, 171,04 USD, Ziele 190/216 USD, Stopps 160/171,04 USD; Derivat
HS5RMP, 0,17 EUR, Ziele 0,70/2,30 EUR, Laufzeit 16.01.2026.
SQLite-Numeric-Rundungsreste werden nur für die Anzeige bis maximal 1e-12
normalisiert; die unveränderten Datenbankwerte stehen separat im Bericht.
Abweichungen werden gesperrt und niemals durch Auftragswerte ersetzt.

Es sind kein autorisierter EODHD-Zugang, keine echten Kursarchive und keine
Hetzner-OpenFIGI-Exporte in dieser Umgebung vorhanden. Daher lautet das Ergebnis
**gesperrt**, mit konkreten Blockern; keine reale Kurszielerreichung und keine
Rendite werden behauptet. Die
[öffentliche Baseline](hebeltrader-jnj-v17-baseline.json) und
[CSV-Prüfliste](hebeltrader-jnj-v17-baseline.csv) sind Original-Metadaten und
Voraussetzungsprüfung, kein abgeschlossener Real-Backtest. Synthetische Tests werden
separat gekennzeichnet und liefern keine historischen Erfolgslabels.

## Bericht und Offline-Befehle

`DATABASE_URL` muss auf eine vorhandene lesbare Datenbank zeigen, möglichst mit
einer bereits eingerichteten SELECT-Rolle. Kein `import`, `review`, `alembic` oder
Scanner-Worker ist erforderlich. Zusätzlich setzt der CLI-Lauf PostgreSQL
`SET TRANSACTION READ ONLY` beziehungsweise SQLite `PRAGMA query_only=ON`.

```bash
python -m scanner.hebeltrader pilot run \
  --run-at 2026-10-22T12:00:00+00:00 \
  --output-prefix reports/hebeltrader/pilot-v17/initial
python -m scanner.hebeltrader pilot verify \
  --output-prefix reports/hebeltrader/pilot-v17/initial
```

Exit 2 bei Blockern ist ein prüfbares Ergebnis: JSON/CSV/Markdown wurden trotzdem
angelegt. Ein Fehler vor der Berichterstellung wird als Fehlerklasse ohne potenziell
geheime HTTP-URL ausgegeben. Existierende Ausgaben werden nie überschrieben.
Vier Dateien entstehen ausschließlich neu mit Modus 0600: `.json`, `.csv`, `.md`,
`.sha256.json`. `verify` prüft Datei-SHAs, Berichts-SHA und inhaltliche Gleichheit
zwischen JSON, CSV und Zusammenfassung. Gleiche Eingaben, Datenbankstände und
Zeitparameter ergeben identische Bytes. SHA-256 ersetzt keine externe Signatur.

Der Bericht trennt:

- **A Originalempfehlung:** Original-SHA/Ordinal, Datenbankwerte, Anzeige,
  Publikationsdatum und Seitenbelege; kein Ersatz durch Werte aus einer Fixture.
- **B Marktdaten:** Archiv, Sitzungen, fehlende Sitzungen, Roh-/Snapshot-Integrität,
  Kalenderquelle, Corporate Actions und jeweilige Freigaben.
- **C Ereignisse:** Jede potenzielle Berührung von Aktienziel 1/2 und Stopp 1/2
  mit Datum, OHLCV, Quellmanifest und Snapshot. Ein berührter Stopp 2 ist noch kein
  aktiver Modellstopp. Unverifizierte Identitäten/Kalender werden sichtbar markiert.
- **D Aktienmodell:** Ausschließlich nach vollständig belegten Freigaben; Einstieg,
  Teilverkäufe, Stopp-/Exit-Ereignisse, Brutto-Preisrendite und V1.6-Drawdown.
- **E Qualität:** gesperrt, nur Forschung oder vollständig auswertbares
  **hypothetisches Aktienmodell**; offene/mehrdeutige Fälle werden nicht als
  vollständig auswertbar ausgegeben. Kein bestätigter Optionsscheinerfolg.

Der zusätzliche Aktienkurs-Pfad zeigt Schlusskurs-Drawdown und die längste Folge
vollständiger Schlusskurse unter dem ersten zulässigen Eröffnungskurs. Er gilt für
das beobachtete Kursfenster, unabhängig vom tatsächlichen Modell-Haltezeitraum.
171,04 USD ist der PDF-Referenzkurs, kein garantierter Einstieg. Der Modell-Einstieg
ist das erste zulässige Open; `after_target1=entry` meint diesen modellierten
Einstieg, nicht automatisch den PDF-Stopp 2.
Er ist keine Strategie-Rendite und kein präziser Intraday-Drawdown. Im Modell bleibt
die V1.6-Metrik der beobachteten Positionswerte separat erhalten.

## Identität und vorhandene OpenFIGI-Exporte

JNJ / JNJ.US, ISIN US4781601046, XNYS, USD und America/New_York sind zunächst nur
Kandidaten aus dem Auftrag. Ein heutiger OpenFIGI-Treffer wird nicht rückwirkend
verifiziert. Datierte Emittentenunterlagen, Börsenunterlagen und historische
Kennungsquellen auf Zeitraum und WKN-/ISIN-/Ticker-Zusammenhang prüfen. Startpunkte
für diese manuelle Recherche sind die J&J-Investor-Relations-SEC-Unterlagen und die
NYSE-Instrumentseite; sie wurden hier nicht als historische Belege abgerufen.
Ein SEC-Tickersymbol allein beweist beispielsweise keine deutsche WKN-Zuordnung.

Die vorhandenen Exporte bleiben unverändert. Dieselben Flags wie beim V1.6-Audit
werden unterstützt:

```bash
python -m scanner.hebeltrader pilot run \
  --openfigi reports/hebeltrader/preparation-v14/openfigi.json \
  --openfigi-cache reports/hebeltrader/preparation-v14/openfigi-raw \
  --linked-identities reports/hebeltrader/preparation-v14/preparation-openfigi.identities.json \
  --historical-sources reports/hebeltrader/pilot-v17/input/historical-sources.json \
  --map reports/hebeltrader/pilot-v17/input/reviewed-map.json \
  --run-at 2026-10-22T12:00:00+00:00 \
  --output-prefix reports/hebeltrader/pilot-v17/identity-audit
```

Historische Quellen und Mapping entsprechen dem
[V1.5-Format](hebeltrader-historical-v15.md): jedes bestätigte Feld hat einen
Payload-SHA und JSON-Pointer, Reviewer und datierten Prüfzeitpunkt. Es gibt keine
neue automatische Identitätsbestätigung. Der Pilot erhält alle gezielt passenden
Quellrecords und das manuelle Mapping für die spätere Nachprüfung im Bericht.
Mehrdeutige Zuordnungen, abweichende Währung oder Börsenidentität sperren das Modell.
US-EODHD-Daten sind keine Belege ausführbarer MIC-spezifischer Börsenquotes.

## EODHD sammeln, normalisieren und wiederholen

Erst einen passenden Zugang und die Nutzungsrechte separat genehmigen lassen.
Kein Abonnement wird durch diese Anwendung gebucht. `EODHD_API_TOKEN` kommt nur aus
einer sicheren Umgebung; keine Schlüssel in Befehlszeilen, JSON oder Git speichern.
Die gesamte externe Monatsausgabe muss innerhalb 100 EUR liegen. Das deklarierte
Budget und die protokollierten API-Einheiten ersetzen keine Anbieterrechnung.

Folgender Befehl ist **nur nach ausdrücklicher Abruffreigabe** vorgesehen:

```bash
python -m scanner.hebeltrader historical-data collect \
  --cache-dir reports/hebeltrader/pilot-v17/raw \
  --symbol JNJ.US --from 2025-08-04 --to 2026-01-16 \
  --endpoints eod splits div \
  --allow-network --authorize-provider-usage \
  --max-requests 6 --max-api-units 6 --monthly-total-eur 100 \
  --output reports/hebeltrader/pilot-v17/input/raw-manifests.json
```

Der 04.08. ist ein Puffer für die belegte Publikationszeitzone; ausgewertet werden
nur zulässige spätere Sitzungen. Das Fenster endet am 16.01.2026, ohne daraus einen
Aktienverkauf oder Erfolg abzuleiten. Der Collector verwendet unveränderliche
Rohantworten, Wiederholungsgrenzen, Cache und das V1.6-Verbrauchsjournal. Bei
Cachetreffern sind keine neuen Netzwerkanfragen erforderlich.

Aus einem unabhängig belegten NYSE-Kalender `sessions.csv` bereitstellen:
`timestamp,end_timestamp`, jeweils mit korrektem New-York-UTC-Offset. Feiertage,
verkürzte Sitzungen und DST müssen belegt sein; kein automatisch erzeugter
Montag-bis-Freitag-Kalender darf als historischer Börsenkalender ausgegeben werden.
Die unveränderte Kalenderquelle unter `raw/` archivieren und ihren SHA festhalten.
Die Kalenderfreigabe bindet Quelle, Lizenz, Quellen-/CSV-SHA, Zeitraum, Reviewer und
Zeitstempel. Fehlt eine Sitzung in den Kursdaten, bleibt die Reihe gesperrt.

```bash
python -m scanner.hebeltrader historical-data normalize \
  --cache-dir reports/hebeltrader/pilot-v17/raw \
  --raw-manifests reports/hebeltrader/pilot-v17/input/raw-manifests.json \
  --spec reports/hebeltrader/pilot-v17/input/spec.candidate.json \
  --calendar reports/hebeltrader/pilot-v17/input/sessions.csv \
  --data-root reports/hebeltrader/pilot-v17/data \
  --run-at 2026-10-22T12:00:00+00:00 \
  --output reports/hebeltrader/pilot-v17/input/bundle.json
```

Die [Spec-Vorlage](examples/jnj-v17.spec.candidate.json) ist ausdrücklich ungeprüft.
Sie bestätigt keine historische Identität. Echte Quellen ergänzen und das
geprüfte Mapping an den entstandenen Snapshot binden. `run-at` muss mindestens der
tatsächliche Archiv-Abrufzeitpunkt sein; feste Werte dienen der Reproduzierbarkeit,
nicht dem Zurückdatieren neuer Daten. API-Lizenzen begrenzen Speicherung/Weitergabe;
Rohdaten gehören nicht automatisch in den PR.

Dividenden und Splits bleiben vollständig im Roharchiv. Nur eine explizite,
manifestgebundene Freigabe kann für diesen Piloten **Cash-Dividenden aus der reinen
Preisrechnung ausschließen**; keine Total-Return-Rendite oder reinvestierte
Dividende wird behauptet. Ohne diese Freigabe blockieren Dividenden wie bisher.
Splits und unbekannte Actions bleiben gesperrt. Die normalen V1.5/V1.6-Provider
werden nicht gelockert. Zusätzlich prüft V1.7, dass normalisierte OHLCV-Werte und
Action-Daten tatsächlich zu den Rohantworten passen, selbst bei konsistenten
Einzeldatei-Hashes.

## Manuelle Regel- und Modellentscheidung

Auf Seite 1/3 beziehen sich die genannten Verkaufsregeln ausdrücklich auf das
Derivat. „20 Tage oder länger im Minus“ unterscheidet dort nicht Kalender- und
Handelstage und klärt den Verlustbezug nicht vollständig. Keine Einheit wird geraten.
Auf Seite 6 enthält das Dokument zusätzlich allgemeine Grundsätze, etwa eine spätere
Stoppanpassung und Einstiegsvorsicht. Deren Verhältnis zu diesem begrenzten
Vier-Regeln-Modell muss ein Mensch dokumentieren. V1.7 ignoriert sie nicht
stillschweigend und behauptet keine vollständige Replikation aller Originalregeln.

Vorlagen sind durchgehend **pending**, keine fertigen Freigaben:

- [Vier-Regeln-Sidecar](examples/jnj-v17.rules.pending.json)
- [Übertragung auf das hypothetische Aktienmodell](examples/jnj-v17.projection.pending.json)
- [Kalenderfreigabe](examples/jnj-v17.calendar.pending.json)
- [Preisrechnung bei Cash-Dividenden](examples/jnj-v17.actions.pending.json)

V1.6-Regel-Sidecar mit Originalzitaten und Seitenbelegen vervollständigen. Die
separate Projektionsfreigabe muss Original-SHA/Ordinal, Reviewer, Zeitpunkt,
`original_rule_scope=derivative`, `model_scope=hypothetical_stock`, eine konkrete
`scope_decision` und `additional_document_rules_reviewed=true` enthalten. Ihr
`rule_spec_sha256` ist der SHA-256 von `eodhd.canonical()` des **einzelnen**
Regelobjekts, nicht der gesamten Schlüsseldatei. Änderungen der Regel machen die
alte Projektionsfreigabe ungültig.

Kalenderfreigabe: `source_file` relativ zu `--eodhd-cache`, Quellen-SHA,
`calendar_sha256` des normalisierten Kalenders, Source-Referenz/Lizenz,
`source_retrieved_at`, Reviewzeit und vollständig geprüfter Zeitraum. Actionfreigabe:
`raw_manifests.splits/div` exakt aus dem verwendeten Bundle. Freigaben haben jeweils
`status=approved`, menschlichen Reviewer und einen nicht zukünftigen Prüfzeitpunkt.
Keine Datenbankzeile wird dabei überschrieben.

Für mehrdeutige „Tage“ ist selbst eine manuelle `time_unit_interpretation` nur eine
Forschungsannahme. Der verifizierte Modus bleibt gesperrt. `loss_basis` muss
Gesamtposition inklusive Teilverkaufserlös oder nur Restbestand ausdrücklich
festlegen. Ein Verlustsignal am vollständigen Schlusskurs kann frühestens zur
nächsten Sitzungseröffnung ausgeführt werden. Bei Stopp/Ziel in derselben Tageskerze
liefert V1.6 nur eine konservative Untergrenze, keine eindeutige Rendite.

```bash
python -m scanner.hebeltrader pilot run \
  --run-at 2026-10-22T12:00:00+00:00 \
  --historical-sources reports/hebeltrader/pilot-v17/input/historical-sources.json \
  --map reports/hebeltrader/pilot-v17/input/reviewed-map.json \
  --rules reports/hebeltrader/pilot-v17/input/rules.json \
  --projection-review reports/hebeltrader/pilot-v17/input/projection.json \
  --calendar-review reports/hebeltrader/pilot-v17/input/calendar-review.json \
  --action-review reports/hebeltrader/pilot-v17/input/actions-review.json \
  --bundles reports/hebeltrader/pilot-v17/input/bundle.json \
  --data-root reports/hebeltrader/pilot-v17/data \
  --eodhd-cache reports/hebeltrader/pilot-v17/raw \
  --output-prefix reports/hebeltrader/pilot-v17/research-001
```

Optional OpenFIGI-Flags ergänzen. Für die strenge Gegenprüfung separat
`--analysis-mode verified` und einen neuen Ausgabepräfix verwenden. Unbekannte
Originalverfügbarkeit bleibt ein Blocker im verifizierten Modus.
`--end-date 2026-10-21` ist eine **separate reine Aktienfortsetzung**: neue vollständige
Kurs-/Action-/Kalenderabdeckung, Gültigkeitsbelege und gebundene Freigaben erforderlich.
Die Optionsscheinlaufzeit wird dadurch nicht verlängert. `--synthetic` ist nur für
klar markierte Tests; ein anderer Dokument-SHA ist ausschließlich dann erlaubt.

## Konkrete Hetzner-Befehle (hier nicht ausgeführt)

Projekt `/opt/aktien-chancen-scanner-v5`, Image `chancen-scanner-v6:local`.
Das bestehende interne Backend-Netzwerk benötigt für den Offline-Bericht keinen
externen DNS-Zugriff. Datenbankzugriff und externen Collector getrennt ausführen;
keine Netzwerke oder bestehenden Container umkonfigurieren. Das Image muss die
V1.7-Dateien bereits enthalten; diese Anleitung baut oder installiert es nicht.

```bash
cd /opt/aktien-chancen-scanner-v5
install -d -m 0700 reports/hebeltrader/pilot-v17
install -d -m 0700 reports/hebeltrader/pilot-v17/input
install -d -m 0700 reports/hebeltrader/pilot-v17/raw
install -d -m 0700 reports/hebeltrader/pilot-v17/data
```

`/sicherer/pfad/pilot-db.env`: ausschließlich die vorhandene Testdatenbank-Verbindung
in `DATABASE_URL`, Host `scanner-v6-postgres-test`, Port 5432. Nicht einchecken und
nicht anzeigen. Nur bestehende SELECT-Zugangsdaten verwenden. Der erste Bericht:

```bash
docker run --rm --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
  --network chancen-scanner-v6_backend \
  --env-file /sicherer/pfad/pilot-db.env \
  --mount type=bind,src="$PWD/reports/hebeltrader/pilot-v17",dst=/pilot \
  --mount type=bind,src="$PWD/reports/hebeltrader/preparation-v14",dst=/openfigi,readonly \
  chancen-scanner-v6:local python -m scanner.hebeltrader pilot run \
  --openfigi /openfigi/openfigi.json --openfigi-cache /openfigi/openfigi-raw \
  --linked-identities /openfigi/preparation-openfigi.identities.json \
  --run-at 2026-10-22T12:00:00+00:00 --output-prefix /pilot/initial-001
```

Für vollständige Läufe die lokalen Dateipfade aus dem vorherigen Beispiel auf
`/pilot/input`, `/pilot/raw` und `/pilot/data` umstellen. Die einmaligen Analysebefehle verwenden mit `--user` die aufrufende Host-UID/GID,
damit vorhandene lesbare Exporte und das neue geschützte Pilotverzeichnis ohne
Änderung ihrer Zugriffsrechte genutzt werden können. Der Standardbenutzer des Images
(UID 10001) und bestehende Container werden dadurch nicht verändert. Die aufrufende
Identität muss die Exporte und die neu geschriebenen Berichte lesen dürfen.

Die bekannte DNS-Einschränkung ohne API-Aufruf prüfen:

```bash
docker run --rm --user "$(id -u):$(id -g)" --read-only --network chancen-scanner-v6_backend \
  chancen-scanner-v6:local python -c \
  'import socket; print("db_dns", bool(socket.getaddrinfo("scanner-v6-postgres-test",5432)))'
docker run --rm --user "$(id -u):$(id -g)" --read-only --network host chancen-scanner-v6:local python -c \
  'import socket; print("eodhd_dns", bool(socket.getaddrinfo("eodhd.com",443)))'
```

Das zweite Kommando löst nur DNS auf; es ruft keine Kurse ab. Auf diesem
Standalone-Hetzner-Server kann nach separater Freigabe der reine Collector kurzlebig
mit Host-Netz laufen; er startet keine Ports, verbindet keine Datenbank und
verändert keine Netzwerkdefinition. Kein Umgehen einer Cloud-Netzwerkpolicy.
Der Offline-Bericht läuft weiterhin im bestehenden Backend-Netz.

```bash
# Ausschließlich nach separater Abruffreigabe und mit genehmigtem Anbieterzugang:
docker run --rm --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp --network host \
  --env-file /sicherer/pfad/pilot-eodhd.env \
  --mount type=bind,src="$PWD/reports/hebeltrader/pilot-v17",dst=/pilot \
  chancen-scanner-v6:local python -m scanner.hebeltrader historical-data collect \
  --cache-dir /pilot/raw --symbol JNJ.US --from 2025-08-04 --to 2026-01-16 \
  --endpoints eod splits div --allow-network --authorize-provider-usage \
  --max-requests 6 --max-api-units 6 --monthly-total-eur 100 \
  --output /pilot/input/raw-manifests.json
```

`pilot-eodhd.env` enthält ausschließlich den sicher gespeicherten `EODHD_API_TOKEN`,
keine DB-Zugangsdaten. Normalisierung und spätere Reproduktion können mit
`--network none`, ohne DB-/API-Umgebung, erfolgen; für die reine Paketprüfung gilt:

```bash
docker run --rm --user "$(id -u):$(id -g)" --read-only --network none \
  --mount type=bind,src="$PWD/reports/hebeltrader/pilot-v17",dst=/pilot,readonly \
  chancen-scanner-v6:local python -m scanner.hebeltrader pilot verify \
  --output-prefix /pilot/research-001
```

## Tests

Die Offline-Fixtures enthalten ausschließlich synthetische OHLCV-, Kalender- und
Identitätsdaten. Abgedeckt sind exaktes SHA-/Ordinal-Laden, Abweichungen von
Originalwerten, fehlende Sitzungen, Feiertags-/Halbtag-/DST-Verarbeitung,
manifestgebundene Dividendenausnahme, Split-Sperre, Raw-/Snapshot-Parität,
20-Tage-Verlustsignal, nächstes Open, profitable offene Position, Gap, Tageskerzen-
Mehrdeutigkeit, Scope-Freigabe, strenger Modus und identische Offline-Wiederholung.
Die feste 118er-Regression und alle bisherigen Tests bleiben erhalten.

```bash
ruff check .
ruff format --check .
python -m pytest -q
POSTGRES_PASSWORD=local-disposable-test docker compose --profile analysis config --quiet
docker build -t scanner-v17-check .
```

Vollständige PostgreSQL-/Docker-Abnahme erfolgt zusätzlich in GitHub Actions auf
wegwerfbaren Testressourcen. Keine der Prüfungen benötigt produktive Datenbanken,
einen Live-Scanner oder bezahlte Kursabfragen.

### Lokale Abnahme des Entwicklungsstands

Ruff und Formatprüfung erfolgreich; Modul-/Identitätssuite: **218 bestanden,
6 übersprungen** (kein lokaler PostgreSQL-Testserver). Ein vollständiger lokaler
pytest-Versuch wurde nach 35 Sekunden im HTTP/TestClient-Bereich beendet und gilt
nicht als vollständiger Erfolg. Der Docker-Build wurde versucht, ist lokal durch
die Sandbox/Docker-Konfiguration gesperrt. Vollständige pytest-, PostgreSQL- und
Docker-Ergebnisse werden deshalb über die zum PR verlinkten Actions-Läufe belegt.

Die echten Original-Metadaten wurden zweimal mit identischen Zeitparametern geprüft;
JSON, CSV, Markdown und Hashindex waren byteidentisch. Datenbank-SHA vor/nach beiden
Läufen: `812be771674f3c207d2e2a5b6087242260e0a80d1c51c270c58b61c77de3ab79`.
Geschützte vollständige Berichte: `/workspace/artifacts/hebel-jnj-v17/pilot-003.*`
und `pilot-004.*`; öffentliche Projektion ohne Originalzitate:
`docs/hebeltrader-jnj-v17-baseline.*`. Das sind Eingangsprüfungen mit Blockern,
keine Ergebnisse aus echten EODHD-Kursreihen. Die 118er-Regressionsbasis bleibt erhalten.
