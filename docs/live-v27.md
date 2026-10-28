# V2.7 – SEC-Live-Pilot

Status: begrenzter Pilot, keine Produktionsfreigabe. Siehe [Abnahme](live-v27-acceptance.md).
Die kleinste Pipeline verwendet bestehende SEC-Identitäten, SEC-Submission-Normalisierung,
Tiingo-Archivierung, Gratis-Quota-Ledger und technische Features. Keine Orders.

## Verhalten

Jeder Lauf lädt ein frisches SEC-Universum und mindestens 100 eindeutig gelistete
Emittenten von Nasdaq/NYSE/NYSE American. Auswahl unabhängig von historischen
Kursarchiven mit vorhandenem stabilen SHA256-CIK-Verfahren. Fonds-Namensmuster,
Mehrfachlistings und nicht unterstützte Börsen werden ausgewiesen. Diese Stichprobe
belegt keine bestimmte Branchen-, Größen- oder vollständige US-Marktabdeckung.
Universum und Ausschlussliste werden bei jedem Lauf archiviert.

Alle 100 Submissions werden vor der begrenzten Detailbewertung abgefragt. Neue
Meldungen werden dauerhaft erfasst; höchstens zehn erhalten pro Lauf Originaldokument-
und Kursprüfung. Neue Meldungen werden zuerst bewertet; danach bisher nicht oder
am längsten nicht bewertete Ereignisse. Budgetbedingt vertagte Meldungen bleiben
sichtbar. Wiederholungen erhalten keinen neuen Entdeckungszeitpunkt, können aber
mit inzwischen verfügbaren Kursen neu bewertet werden.

SEC `acceptanceDateTime` ist der SEC-Veröffentlichungszeitpunkt, möglicherweise
später als die ursprüngliche IR-Mitteilung. Die Vorlaufzeit wird ausdrücklich nicht
als frühester Nachrichtenzeitpunkt behauptet. Primärdokument und Rohantworten sind
hashgebunden; eine 8-K-Itemnummer oder ein Schlüsselwort beweist keine positive
Überraschung. Anlagen/Exhibits werden noch nicht ausgewertet. Finanzielle Größen,
Original-IR-Zeitpunkt und fundamentale Relevanz bleiben ungeprüft.

Mit autorisiertem Tiingo-Zugang: historische OHLCV, 1/5/10/20-Sitzungsrenditen,
Volumenverhältnis, Dollar-Liquidität, ATR, Trend, Ausbruch, SPY-Stärke, soweit vollständig.
Ohne verifizierten Börsenkalender werden weder heutige Tagesdaten noch der
Publikationstag zur Vorher-/Nachher-Reaktion verwendet. Reaktion = letzte EOD-
Beobachtung vor dem lokalen Publikationstag gegenüber letzter abgeschlossener
EOD-Beobachtung nach diesem Tag. Das ist eine vorsichtige Mehrtagesreaktion, keine
isolierte kausale Wirkung und keine Intraday-Messung. Feiertage/erste Handelsmöglichkeit
werden nicht aus Werktagen geraten. Ein verifizierter Kalender ist weiterhin nötig.

Entscheidungen:

- `NICHT VERFÜGBAR`: kein Kursbeleg verfügbar.
- `BEOBACHTEN`: EOD-/Research-Kontext, aktuelle ausführbare Quotes oder Bestätigung fehlen.
- `ABLEHNEN`: beispielsweise SEC-Item 3.02/Emissionsformular als Verwässerungsrisiko,
  über 15 % bereits beobachteter Mehrtagesanstieg oder Dollar-Liquidität unter 1 Mio. USD.

Der Pilot unterstützt **kein KAUF-LIMIT**. Einstieg/Stopp/Ziele/Netto-CRV bleiben null;
keine künstlich konstruierten 2:1-ATR-Ziele. Vor einem Kaufalarm fehlen Live-Quote mit
Lizenz/Zeitstempel, vollständige Identität/ISIN, Kalender, fundamentale Primärbestätigung,
belegte Ziel-/Invalidationslevel und Kosten-/Spreadprüfung. Netto-CRV muss dann mindestens
2 betragen. flatex Österreich bleibt ungeprüft. Strategie B wird nicht durch Momentum
ersetzt, sondern ausdrücklich als nicht bewertet ausgewiesen.

## Lokal reproduzieren

Python 3.12; vorhandene Projektabhängigkeiten installieren:

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m scanner.live_pilot scan --root ./data/live-v27
.venv/bin/python -m scanner.live_pilot verify --root ./data/live-v27
.venv/bin/python -m scanner.live_pilot export --root ./data/live-v27 > ./data/live-v27/export.json
```

SEC benötigt `SEC_USER_AGENT` mit echtem Namen/Anwendung und Kontakt-E-Mail.
Fehlt sie, erfolgt kein SEC-Abruf; Exitcode 2 plus dauerhaftes `blocked`-Protokoll.
Ein vollständig abgearbeiteter Scan liefert Exitcode 0, was **keine erfolgreiche
fachliche Live-Abnahme oder Kaufbereitschaft** bedeutet. Einzelne Datenfehler sind
im Journal sichtbar. Für Tiingo sind `TIINGO_API_TOKEN`, bereits bestehende zulässige
Nutzungsrechte und `--authorize-tiingo` nötig. Kein Kauf eines Tarifs.

Parameter: `--count 100`, `--max-events 10`, `--lookback-hours 72`,
`--max-requests 150`, `--max-seconds 180`. Gemeinsames Requestbudget einschließlich
Retries; SEC max. 8 Requests/Sekunde, 403/429 stoppen den gemeinsamen Abruf.
Tiingo reserviert zusätzlich konservativ drei Requests pro Symbol vor dem Abruf:
maximal 50/Stunde, 1000/Tag, 500 verschiedene Symbole/Monat. Andere Anwendungen
mit demselben Token müssen dieselbe Quota berücksichtigen. Keine KI-API-Aufrufe,
keine zusätzlich kostenpflichtigen Quellen, zusätzliche geplante Kosten 0 EUR.

## Docker/Hetzner: nur manuell nach Review

Das separate Compose-Projekt verwendet ausschließlich ein explizites neues
Bind-Verzeichnis. Keine Immich-Container, fremden Volumes, Datenbanken, Migrationen
oder bestehenden Compose-Dateien werden geändert. Noch kein Deployment durchgeführt.

```sh
cp .env.live-v27.example .env.live-v27
chmod 600 .env.live-v27
# Datei lokal mit echten Zugangsdaten befüllen, nicht committen.
mkdir -p ./data/live-v27
# Verzeichnis für UID/GID 10001 schreibbar machen oder SCANNER_UID/SCANNER_GID
# auf einen passenden nicht privilegierten Hostbenutzer setzen.
docker compose --env-file .env.live-v27 -f compose.live-v27.yaml build pilot
# Zuerst Einzellauf (Exitcode 2 bei Blockern):
docker compose --env-file .env.live-v27 -f compose.live-v27.yaml run --rm pilot \
  python -m scanner.live_pilot scan
# Optional nach Prüfung vorhandener Gratisrechte: Einzellauf mit --authorize-tiingo.
# Dauerbetrieb erst nach Freigabe:
docker compose --env-file .env.live-v27 -f compose.live-v27.yaml up -d pilot api
```

Für dauerhafte Tiingo-Abfragen muss `--authorize-tiingo` ausdrücklich zur
Pilot-Command-Liste ergänzt werden. Standardintervall 900 Sekunden, mindestens 300;
konfigurierbar über CLI. Laufzeit und Quoten begrenzen Datenabrufe. Restart-Policy,
exklusives Prozess-Lock, atomare Journaltransaktionen und Erkennung unvollständiger
Läufe erlauben Wiederaufnahme. Der Lookback ist beschränkt: Ausfälle über 72 Stunden
können Meldungen verpassen; maximal 168 Stunden konfigurierbar. Keine Vollständigkeitsbehauptung.

Lesende API: `http://127.0.0.1:8270/health`, `/scans`, `/decisions?limit=50`.
API hat den Datenträger nur lesend. Kein öffentlicher Port, keine Schreib-/Orderroute.
Für entfernten Zugriff SSH-Tunnel verwenden. Benachrichtigungen sind deaktiviert,
weil noch keine qualifizierten Kaufalarme möglich sind.

## Nachweis und Grenzen

`audit.db` enthält Start/Ende, Erreichbarkeit/HTTP-Status, Universum, geprüfte Emittenten,
neue Meldungen, Ausschlüsse, Vertagungen, Evidenz, Datenfehler und zeitgestempelte
Entscheidungen. Hashkette und SQLite-Trigger verhindern normale Änderungen und
machen Inhaltsmanipulationen nachweisbar. Administratoren können Datenbank/Trigger
ersetzen oder die Kette am Ende kürzen. Für echte Unveränderbarkeit ist ein separater
WORM-/Object-Lock-Speicher oder ein extern zeitgestempelter Hashanker erforderlich.
Die Software allein bietet diesen administrativen Schutz nicht. Regelmäßig Export
und Journal-Endhash extern sichern; Rohdaten/Journal nicht löschen oder rotieren.
Laufende Änderungen lassen sich im Folgescan prüfen, vergangene Entscheidungen
bleiben erhalten. Eine automatische nachgelagerte Performance-/Fill-Auswertung ist
noch nicht implementiert; keine Trefferquote.

Steyr Motors ist ein expliziter Abdeckungsfehler dieser US-SEC-Stichprobe, kein
rückwirkend erkannter Treffer. Es existiert hier kein vor dem Anstieg ausgegebenes
Signal und keine belegte historische Live-Scan-Historie. Daher lassen sich die fünf
geforderten Erfolgs-/Fehlerklassen noch nicht seriös quantifizieren. Weitere verpasste
Chancen erfordern datierte Originalmeldungen, Kursdaten und damalige Scanprotokolle.
DACH (EQS/IR/Börsen), Sentiment-Communities, Investmentstrategie B und Derivate werden
entsprechend dem Auftrag erst nach bestandener realer Pilotabnahme erweitert.
Für keine dieser Quellen werden Zugang, Lizenz oder Abdeckung behauptet.

Budget und Wiederanlauf: Unzureichende Kombinationen aus Universumgröße und
Requestbudget werden vor Netzwerkzugriff zurückgewiesen. Detailkapazität wird
mit eingeplant; Retries können trotzdem einen Lauf verkürzen. Nach Unterbrechungen
beginnt der Folgelauf hinter dem zuletzt versuchten Emittenten. Erfolgreiche
Kursantworten werden innerhalb eines Laufs pro Symbol wiederverwendet, ohne erneut
Gratisquota zu reservieren. Die kooperative Deadline wird vor jedem Abruf und beim
Empfang geprüft; laufendes HTTP-I/O kann bis zum begrenzten Phasen-Timeout nachlaufen.
