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

- stabile Asset-ID, CIK, Ticker, Börse, MIC, Währung, Zeitzone und Providersymbol;
- Sessiondatum und expliziten regulären Schlusszeitpunkt;
- rohe und adjustierte OHLCV-Vektoren getrennt;
- Dividenden und Splits als eigene Corporate Actions;
- Abrufzeit, modellierte Verfügbarkeit, Quelle, Lizenzreferenz sowie Raw-/Manifest-SHA-256;
- Bid/Ask nur als tatsächlich beobachtete Quote. EOD-OHLCV erzeugt keine Quote und keinen
  Spread.

Ein normalisierter EOD-Wert gilt nicht als Beleg seiner damaligen historischen Verfügbarkeit.
`strict` zeigt nur Revisionen, die bis `as_of` tatsächlich abgerufen waren. `modeled` kann den
Sessionschluss als hypothetische Verfügbarkeit verwenden, bleibt aber
`historical_availability_verified=false` und `training_eligible=false`. Ohne unabhängigen
Börsenkalender werden fehlende Sitzungen nicht aus Wochentagen abgeleitet.

## Idempotenz und Korrekturen

`MarketDataArchive` ist ein separates SQLite-Artefakt. Identische Providerzeilen werden nicht
dupliziert. Geänderte Werte erzeugen eine neue Revision; frühere Revisionen und ihre Raw-/Manifest-
Hashes bleiben erhalten. Ein erneut eingespielter alter Stand setzt die letzte Revision nicht
zurück. Eine geänderte CIK-/Ticker-/MIC-/Währungszuordnung für dieselbe Asset-ID stoppt den Import.

Der Pilot fragt nach einem vorhandenen letzten Sessiondatum nur den nachfolgenden Zeitraum ab.
Damit werden regulär nur neue Zeilen geladen; Providerkorrekturen innerhalb eines bereits
archivierten Zeitraums müssen bewusst durch erneuten Import des betreffenden Raw-Snapshots
eingespielt werden.

## Reproduzierbarer Serverlauf

Voraussetzung ist ein mit V2.4 gebauter, SHA-verifizierter Research-Index mit mindestens zehn
sichtbaren US-Aktien. Der Pilot wählt zehn eindeutige CIK per
`stable_sha256_sec_cik_v1`; Name, Teaser oder erwartetes Ergebnis beeinflussen die Auswahl nicht.
Bekannte Fonds werden ausgeschlossen. Unbekannte Instrumenttypen bleiben sichtbar und werden im
Coverage-Bericht ausgewiesen.

Nur wenn ein bereits berechtigter kostenloser Tiingo-Zugang vorhanden ist:

```bash
cd /opt/aktien-chancen-scanner-v5
export TIINGO_API_TOKEN='aus-sicherem-secret-store'
python -m scanner.market_data.cli pilot \
  --index reports/research-v24/index.db \
  --market-db reports/market-data-v251/market-data.sqlite \
  --raw-cache reports/market-data-v251/tiingo-raw \
  --output reports/market-data-v251/coverage \
  --start 2025-01-01 \
  --end 2025-12-31 \
  --as-of 2026-10-24T12:00:00+00:00 \
  --count 10 \
  --max-requests 30 \
  --max-duration-seconds 120 \
  --monthly-cost-eur 0 \
  --allow-network \
  --authorize-provider-usage
```

Die beiden letzten Flags sind unabhängig erforderlich. `--max-requests 30` erlaubt höchstens drei
Versuche je Titel. Ein Kostenwert über 20 EUR wird abgewiesen. Der Befehl schreibt Coverage als
kanonisches JSON und CSV sowie den JSON-SHA in die Konsolenausgabe. Zugangsdaten erscheinen weder
im Archiv noch im Bericht.

Offline-Replay eines bestehenden Raw-Archivs lässt beide Freigabeflags weg:

```bash
python -m scanner.market_data.cli pilot \
  --index reports/research-v24/index.db \
  --market-db reports/market-data-v251/replay.sqlite \
  --raw-cache reports/market-data-v251/tiingo-raw \
  --output reports/market-data-v251/replay-coverage \
  --start 2025-01-01 --end 2025-12-31 \
  --as-of 2026-10-24T12:00:00+00:00 \
  --count 10 --max-requests 10 --monthly-cost-eur 0
```

Der Bericht unterscheidet verfügbare Adapter von erfolgreich verwendeten Quellen. Er enthält pro
Titel Status, Sitzungszahl, 250-Sitzungen-Schwelle, Actions, Abrufzeit und SHA-Belege. Solange kein
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
