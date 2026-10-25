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
externer Blocker dieser Entwicklungsumgebung. Am 25. Oktober 2026 wurde der isolierte Hetzner-
Pilot anschließend mit einem erneuerten, nur zur Laufzeit eingegebenen Tiingo-Schlüssel real
ausgeführt: 9 von 10 Titeln wurden importiert, davon 8 mit 250 Sitzungen. Der Gesamtstatus ist
korrekt `partial`; Details und Grenzen stehen im
[Live-Pilotbericht](market-data-v251-hetzner-pilot.md). Offline-Tests mit 10 synthetischen Titeln
und jeweils 250 Zeilen prüfen weiterhin ausschließlich Verarbeitung und Reporting.
Der kanonische [Workspace-Coverage-Bericht](market-data-v251-codex-coverage.json), seine CSV und
SHA-256-Sidecar halten diesen Nullbefund reproduzierbar fest; sie enthalten keine erfundenen Titel.
Der Workspace-Bericht beschreibt ausschließlich die Codex-Umgebung und wird durch den späteren
Serverlauf nicht rückwirkend umgedeutet.

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

### Einfacher Hetzner-Lauf

Ein früher über Chat geteilter Schlüssel darf nicht verwendet werden. Er wird zuerst im
Tiingo-Konto widerrufen und erneuert. Der neue Schlüssel wird ausschließlich an der verdeckten
Eingabeaufforderung des Runners eingegeben oder vorab über eine geschützte Server-Umgebungsvariable
bereitgestellt. Er gehört weder in diesen Befehlsblock noch in eine `.env`-Datei.

Falls `/opt/scanner-v251-sec-source` noch nicht existiert, wird das öffentliche SEC-Universe mit
genau einer kostenlosen, begrenzten Anfrage in diesem isolierten Verzeichnis archiviert. Die SEC
verlangt dafür einen User-Agent mit Kontaktadresse:

```bash
(
  set -e
  cd /opt/scanner-v251-pr21
  SEC_SOURCE=/opt/scanner-v251-sec-source
  install -d -m 700 "$SEC_SOURCE"
  read -rp 'Kontakt-E-Mail für den SEC User-Agent: ' SEC_CONTACT
  test -n "$SEC_CONTACT"
  export SEC_USER_AGENT="Scanner V6 research contact $SEC_CONTACT"
  docker run --rm --network bridge --user "$(id -u):$(id -g)" \
    -e SEC_USER_AGENT \
    --mount "type=bind,src=$SEC_SOURCE,dst=/sec-source" \
    scanner-v251-pr21 \
    python -m scanner.research_cli \
      --cache-dir /sec-source/sec-cache \
      --output /sec-source/sec-universe.json \
      --allow-network --max-requests 1 sec-universe
  unset SEC_USER_AGENT SEC_CONTACT
)
```

Der Fehlercode der Subshell beendet die SSH-Anmeldung nicht. Das erzeugte Quellarchiv wird beim
anschließenden Tiingo-Pilot nur lesend eingebunden.

Der Runner verwendet das isolierte SEC-Quellverzeichnis ausschließlich als Read-only-Quelle. Er
findet genau ein SHA-geprüftes SEC-Universe-Manifest, baut daraus den Pilotindex und schreibt alle
neuen Dateien nach `/opt/scanner-v251-tiingo-pilot`. Vor dem Providerabruf prüft er, dass Index und
SEC-Audit zusammengehören und der aktuelle `as-of`-Zeitpunkt nicht vor der belegten
SEC-Archivierung liegt. Der gesamte Ablauf lässt sich in Termius als ein Block einfügen; nur der
erneuerte Schlüssel wird anschließend verdeckt abgefragt:

```bash
(
  set -e
  cd /opt/aktien-chancen-scanner-v5
  git fetch origin feat/short-term-market-data-v2-5-1
  if [ ! -e /opt/scanner-v251-pr21/.git ]; then
    git worktree add --detach /opt/scanner-v251-pr21 \
      origin/feat/short-term-market-data-v2-5-1
  else
    test -z "$(git -C /opt/scanner-v251-pr21 status --porcelain)"
    git -C /opt/scanner-v251-pr21 checkout --detach \
      origin/feat/short-term-market-data-v2-5-1
  fi
  cd /opt/scanner-v251-pr21
  unset TIINGO_API_TOKEN
  SOURCE_REPORTS=/opt/scanner-v251-sec-source \
  OUTPUT_DIR=/opt/scanner-v251-tiingo-pilot \
  bash scripts/run-tiingo-pilot.sh
)
status=$?
if [ "$status" -ne 0 ]; then
  echo "Pilot mit Fehlercode $status beendet; die SSH-Sitzung bleibt geöffnet."
fi
```

Der Test nutzt weder Docker Compose noch PostgreSQL und referenziert daher keine Container,
Volumes oder Netzwerke von Immich. Er erlaubt höchstens zehn ausgewählte US-Aktien, 30 Versuche
einschließlich begrenzter Retries und deklarierte Kosten von 0 EUR. Der kostenlose Tiingo-Starter-
Rahmen aus dem Provider-Audit reicht dafür aus; der Ablauf nimmt keine Buchung vor.

Das Abschluss-JSON auf dem Terminal und `/opt/scanner-v251-tiingo-pilot/coverage.json` zeigen:

- `partial` mit erfolgreichen Instrumenten: echter Datenintegrationsnachweis; der unabhängige
  Handelskalender fehlt weiterhin;
- `accepted`: nur mit separat belegtem, SHA-gebundenem Handelskalender erreichbar;
- `blocked`: kein Titel konnte belegt importiert werden, der konkrete Grund steht in
  `blocker_code` und den Instrumentzeilen.

Zusätzlich entstehen `coverage.csv`, `coverage.sha256`, das isolierte SQLite-Archiv und die
unveränderlichen Tiingo-Rohsnapshots. `sha256sum -c coverage.sha256` wird vom Runner ausgeführt.
Der Schlüssel wird weder als Befehlsargument noch in Reports, Raw-Snapshots oder Images
gespeichert und beim Verlassen des Skripts aus dessen Umgebung entfernt.

### Einzelbefehle zur Diagnose

Der folgende ausgeschriebene Ablauf entspricht dem Runner und dient nur zur Diagnose. Er nutzt
das vorhandene Archiv read-only und ein eigenes Ausgabeverzeichnis:

```bash
cd /opt/scanner-v251-pr21
SOURCE_REPORTS=/opt/aktien-chancen-scanner-v5/reports
OUTPUT_DIR=/opt/scanner-v251-tiingo-pilot
docker build -t scanner-v251-pr21 .
install -d -m 700 "$OUTPUT_DIR"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$SOURCE_REPORTS,dst=/source-reports,readonly" \
  --mount "type=bind,src=$OUTPUT_DIR,dst=/output" \
  scanner-v251-pr21 \
  python -m scanner.market_data.cli build-sec-pilot-index \
  --sec-cache-root /source-reports \
  --index /output/sec-pilot-index.db \
  --audit-output /output/sec-pilot-index.audit.json
```

Falls das bestehende Archiv anders liegt, wird ausschließlich `SOURCE_REPORTS` angepasst. Die
automatische Suche verlangt genau ein gültiges Universe-Manifest und prüft dessen Rohdaten-SHA.
Für den Netzwerklauf ist genau eine geheime Variable erforderlich:

```bash
read -rsp 'TIINGO_API_TOKEN: ' TIINGO_API_TOKEN; echo
export TIINGO_API_TOKEN
AS_OF=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
docker run --rm --network bridge --user "$(id -u):$(id -g)" \
  -e TIINGO_API_TOKEN \
  --mount "type=bind,src=$OUTPUT_DIR,dst=/output" scanner-v251-pr21 \
  python -m scanner.market_data.cli pilot \
  --index /output/sec-pilot-index.db \
  --sec-index-audit /output/sec-pilot-index.audit.json \
  --market-db /output/market-data.sqlite \
  --raw-cache /output/tiingo-raw \
  --output /output/coverage \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --as-of "$AS_OF" \
  --count 10 \
  --max-requests 30 \
  --max-duration-seconds 120 \
  --monthly-cost-eur 0 \
  --allow-network \
  --authorize-provider-usage
unset TIINGO_API_TOKEN
cd "$OUTPUT_DIR"
sha256sum -c coverage.sha256
```

Die beiden letzten Flags sind unabhängig erforderlich. `--max-requests 30` erlaubt höchstens drei
Versuche je Titel. Ein Kostenwert über 20 EUR wird abgewiesen. Der Befehl schreibt `coverage.json`,
`coverage.csv` und `coverage.sha256`. Zugangsdaten erscheinen weder im Archiv noch im Bericht.

Für den Status `accepted` ist zusätzlich ein unabhängig archivierter offizieller Kalender nötig.
Die CSV enthält ausschließlich `session_date,close_at`; `close_at` ist ein ISO-8601-Zeitpunkt mit
Offset und bildet auch Early Closes ab. Der Netzwerklauf erhält dann zusätzlich:

```text
--calendar /output/us-equities-calendar.csv
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
