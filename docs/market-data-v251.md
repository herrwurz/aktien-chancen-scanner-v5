# Scanner V6 V2.5.1 – historische Kursdatenpipeline

## Ergebnis und Grenze

V2.5.1 verbindet den lokalen V2.4-Research-Index mit einem isolierten, append-only
SQLite-Kursarchiv. Es enthält keine Strategie, kein Kaufsignal, keinen Backtest und keine Order.
Die produktive PostgreSQL-Datenbank wird nicht gelesen oder verändert.

Tiingo ist der erste US-EOD-Pilot. Ein Abruf liefert rohe und adjustierte OHLCV-Werte sowie
Dividenden- und Splitfelder. EODHD kann über vorhandene unveränderliche Archive normalisiert
werden, benötigt für Preise, Splits und Dividenden aber getrennte Abrufe. Twelve Data und Alpha
Vantage wurden auditiert, in diesem PR jedoch nicht angebunden.

Die Codex-Umgebung enthielt am 24. Oktober 2026 weder einen realen SEC-Index noch
`TIINGO_API_TOKEN`, `EODHD_API_TOKEN`, `TWELVE_DATA_API_KEY` oder
`ALPHA_VANTAGE_API_KEY`. Deshalb wurde **keine reale 10-Aktien-Abdeckung gemessen**. Das ist ein
externer Datenblocker, kein erfolgreiches Akzeptanzergebnis. Offline-Tests mit 10 synthetischen
Titeln und jeweils 250 Zeilen prüfen nur Verarbeitung und Reporting.
Der kanonische [Workspace-Coverage-Bericht](market-data-v251-codex-coverage.json), seine CSV und
SHA-256-Sidecar halten diesen Nullbefund reproduzierbar fest; sie enthalten keine erfundenen Titel.

## Datenvertrag

`scanner.market_data.models` speichert:

- kanonische Asset-ID `cik:<zehnstellige CIK>`, Ticker, Börse, MIC, Währung, Zeitzone und
  Providersymbol;
- Sessiondatum sowie entweder einen SHA-belegten Börsenkalenderschluss oder einen ausdrücklich
  unbestätigten modellierten regulären Schluss;
- rohe und adjustierte OHLCV-Vektoren getrennt;
- Dividenden und Splits als eigene Corporate Actions;
- Abrufzeit, modellierte Verfügbarkeit, Quelle, Lizenzreferenz sowie Raw-/Manifest-SHA-256;
- Bid/Ask nur als tatsächlich beobachtete Quote. EOD-OHLCV erzeugt keine Quote und keinen
  Spread.

Ein normalisierter EOD-Wert gilt nicht als Beleg seiner damaligen historischen Verfügbarkeit.
`strict` zeigt nur Revisionen, die bis `as_of` erstmals im lokalen Archiv gespeichert waren.
Provider-Abruf und erstmalige Speicherung bleiben getrennt. Eine Korrektur ersetzt die frühere
Revision erst ab ihrer eigenen Speicherzeit. `modeled` kann den
Sessionschluss als hypothetische Verfügbarkeit verwenden, bleibt aber
`historical_availability_verified=false` und `training_eligible=false`. Ohne unabhängigen
Börsenkalender werden fehlende Sitzungen nicht aus Wochentagen abgeleitet.

## Idempotenz und Korrekturen

`MarketDataArchive` ist ein separates SQLite-Artefakt. Identische Providerzeilen werden nicht
dupliziert. Geänderte Werte erzeugen eine neue Revision; frühere Revisionen und ihre Raw-/Manifest-
Hashes bleiben erhalten. Ein erneut eingespielter alter Stand setzt die letzte Revision nicht
zurück. Eine geänderte CIK-/Ticker-/MIC-/Währungszuordnung für dieselbe Asset-ID stoppt den Import.
Archive aus einer früheren Schemafassung ohne belegten lokalen Erstspeicherzeitpunkt werden
fail-closed abgewiesen und müssen aus ihren unveränderlichen Raw-Snapshots neu aufgebaut werden;
der Provider-Abrufzeitpunkt wird nicht rückwirkend als Speicherzeitpunkt ausgegeben.

Der Pilot fragt nach einem vorhandenen letzten Sessiondatum nur den nachfolgenden Zeitraum ab.
Damit werden regulär nur neue Zeilen geladen; Providerkorrekturen innerhalb eines bereits
archivierten Zeitraums müssen bewusst durch erneuten Import des betreffenden Raw-Snapshots
eingespielt werden.

## Reproduzierbarer Serverlauf

Voraussetzung ist ein aus dem unveränderten V2.4-SEC-Roharchiv neu gebauter Schema-v3-Pilotindex
mit mindestens zehn sichtbaren US-Aktien. Schema v3 vereinheitlicht CIKs auf zehn Stellen. Der
Builder schließt Mehrfachlistings und unbekannte Börsen mit einem maschinenlesbaren Audit aus,
anstatt willkürlich einen Ticker zu wählen. Der Pilot wählt zehn eindeutige CIK per
`stable_sha256_sec_cik_v1`; Name, Teaser oder erwartetes Ergebnis beeinflussen die Auswahl nicht.
Bekannte Fonds werden ausgeschlossen. Unbekannte Instrumenttypen bleiben sichtbar und werden im
Coverage-Bericht ausgewiesen.

Der folgende Ablauf läuft außerhalb von Compose, verwendet ein eigenes Verzeichnis und Netzwerk
und verändert weder Immich noch PostgreSQL. Zuerst Branch und Image bauen und die archivierte
SEC-Universe-Anfrage eindeutig bestimmen:

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/short-term-market-data-v2-5-1
git worktree add /opt/scanner-v251-pr21 origin/feat/short-term-market-data-v2-5-1
cd /opt/scanner-v251-pr21
docker build -t scanner-v251-pr21 .
install -d -m 700 reports/market-data-v251
SEC_REQUEST=$(grep -rl '"dataset":"universe"' reports/research-v24/sec-cache/requests | head -n 1)
test -n "$SEC_REQUEST"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/reports:/work/reports:rw" scanner-v251-pr21 \
  python -m scanner.market_data.cli build-sec-pilot-index \
  --sec-universe-request "/work/$SEC_REQUEST" \
  --index /work/reports/market-data-v251/sec-pilot-index.db \
  --audit-output /work/reports/market-data-v251/sec-pilot-index.audit.json
```

Falls das bestehende Archiv anders liegt, wird ausschließlich `SEC_REQUEST` angepasst. Der
Indexbuilder prüft den SEC-Rohdaten-SHA. Für den Netzwerklauf ist genau eine geheime Variable
erforderlich. Sie wird verdeckt eingelesen, nur an den einmaligen Container übergeben und danach
entfernt:

```bash
read -rsp 'TIINGO_API_TOKEN: ' TIINGO_API_TOKEN; echo
export TIINGO_API_TOKEN
docker run --rm --network bridge --user "$(id -u):$(id -g)" \
  -e TIINGO_API_TOKEN \
  -v "$PWD/reports:/work/reports:rw" scanner-v251-pr21 \
  python -m scanner.market_data.cli pilot \
  --index /work/reports/market-data-v251/sec-pilot-index.db \
  --market-db /work/reports/market-data-v251/market-data.sqlite \
  --raw-cache /work/reports/market-data-v251/tiingo-raw \
  --output /work/reports/market-data-v251/coverage \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --as-of 2026-10-24T12:00:00+00:00 \
  --count 10 \
  --max-requests 30 \
  --max-duration-seconds 120 \
  --monthly-cost-eur 0 \
  --allow-network \
  --authorize-provider-usage
unset TIINGO_API_TOKEN
cd reports/market-data-v251
sha256sum -c coverage.sha256
```

Die beiden letzten Flags sind unabhängig erforderlich. `--max-requests 30` erlaubt höchstens drei
Versuche je Titel. Ein Kostenwert über 20 EUR wird abgewiesen. Der Befehl schreibt `coverage.json`,
`coverage.csv` und `coverage.sha256`. Zugangsdaten erscheinen weder im Archiv noch im Bericht.

Für den Status `accepted` ist zusätzlich ein unabhängig archivierter offizieller Kalender nötig.
Die CSV enthält ausschließlich `session_date,close_at`; `close_at` ist ein ISO-8601-Zeitpunkt mit
Offset und bildet auch Early Closes ab. Der Netzwerklauf erhält dann zusätzlich:

```text
--calendar /work/reports/market-data-v251/us-equities-calendar.csv
--calendar-mics XNAS,XNYS,XASE
--calendar-timezone America/New_York
--calendar-source-reference <offizielle-archivierte-quellen-url>
--calendar-retrieved-at <tatsächlicher-abrufzeitpunkt-mit-offset>
```

Ohne diesen Beleg bleibt der echte Kursabruf `partial`; Wochentage oder Feiertage werden nicht
geraten. Eine im Providerdatensatz vorhandene Sitzung, die im belegten Kalender fehlt, stoppt den
betroffenen Import.

Offline-Replay eines bestehenden Raw-Archivs lässt beide Freigabeflags weg:

```bash
python -m scanner.market_data.cli pilot \
  --index reports/market-data-v251/sec-pilot-index.db \
  --market-db reports/market-data-v251/replay.sqlite \
  --raw-cache reports/market-data-v251/tiingo-raw \
  --output reports/market-data-v251/replay-coverage \
  --start 2025-01-01 --end 2025-12-31 \
  --as-of 2026-10-24T12:00:00+00:00 \
  --count 10 --max-requests 10 --monthly-cost-eur 0
```

Der Bericht unterscheidet verfügbare Adapter von erfolgreich verwendeten Quellen. Er enthält pro
Titel Status, Datenalter, Sitzungszahl, 250-Sitzungen-Schwelle, getrennte Split-/Dividendenanzahl,
Requests, Fehlerstatus, Abruf-/Speicherzeit und SHA-Belege. Der Gesamtstatus ist ausschließlich
`accepted`, `partial` oder `blocked`. Solange kein
unabhängiger Kalender importiert wurde, bleiben `calendar_status=unavailable_not_inferred` und
`missing_sessions=null`.

## Lokale Prüfung

```bash
ruff check .
ruff format --check .
pytest -q
docker compose config --quiet
docker compose --profile analysis config --quiet
docker build -t scanner-v251 .
```

Ein Fixture-Test ist in der Testdokumentation als `synthetic_fixture` markiert und setzt
`real_provider_coverage_measured=false`. Erst der obige Serverlauf mit einem echten, unveränderten
Providerarchiv darf reale Abdeckung melden.
