# HEBELTRADER-Teaser-Detektiv und separater Marktscanner

Neue [eingefrorene Erstprognose zu HEBELTRADER 198/26](docs/hebeltrader-19826-initial.md):
assistentengestützte Quellenrecherche; die spätere PDF-Auflösung bestätigt SLB auf Rang 1.

[Automatische Erfassung öffentlicher HEBELTRADER-Ausgaben](docs/hebeltrader-catalog-monitor.md):
mit echten Ausgaben und wiederholtem Lauf geprüft; Aktienidentifikation bleibt separat offen.

V3.1 ergänzt ein dauerhaftes Falljournal, spätere Auflösungen, historische Verfügbarkeit
und öffentliche RSS-Entdeckung: [V3.1 Bedienung und Abnahme](docs/teaser-intelligence-v31.md).
Veraltete Tests können append-only archiviert werden. Neue Fälle lassen sich vor der Auflösung
als prospektive Blindtests markieren und nach belegter Auflösung ausdrücklich als prospektive
Referenzen freigeben; die ursprüngliche Rangliste bleibt unverändert.

Primäre Funktion ist die Identifikation unbekannter Aktien aus öffentlichen Teasern:
[Bedienung und Grenzen](docs/hebeltrader-primary.md),
[Abnahmebericht](docs/hebeltrader-primary-acceptance.md). Der Startbildschirm zeigt den
Detektiv; der allgemeine Marktscanner bleibt unter `/market-scanner` erreichbar.

Der neue Recherchepfad nutzt Originalseiten, dieselbe Hinweismatrix für alle Kandidaten,
aktive Gegenrecherche und eine eingefrorene Top-3-Rangliste. Unzureichende Belege führen
zu **nicht identifiziert**. Unabhängige Identifikationsqualität ist noch nicht nachgewiesen.

Die bisherigen [V3-Diagnosewerkzeuge](docs/hebeltrader-detective-v3.md) und der
[Offline-MVP](docs/architecture-hebeltrader-detective-mvp.md) bleiben erhalten; deren sechs
synthetische Adapterunternehmen werden im neuen Primärworkflow nicht verwendet.

Der aktuelle HS5RMP-Derivatepilot ist in
[Scanner V6 V1.8](docs/hebeltrader-hs5rmp-backtest-v18.md) dokumentiert. Ohne autorisierte,
ausreichende Bid-/Ask-Historie wird keine Optionsscheinrendite ausgegeben.

Historisches HEBELTRADER-Modul: [Import, Datenmodell, Prüfung und Deployment](docs/hebeltrader.md).
Es verwendet dieselbe Datenbank mit additiver Migration `0002` und einen optionalen
Compose-Service im Profil `analysis`; der normale Krypto-Scanner bleibt getrennt.

Docker-based Python scanner for crypto, stocks and future leveraged-instrument analysis.

Die V2.5.1-Pipeline für historische US-Aktienkurse, ihr providerneutraler Datenvertrag und der
kontrollierte Tiingo-Pilot sind in [Historische Kursdatenpipeline](docs/market-data-v251.md)
dokumentiert. Ohne echten Provider- und SEC-Index-Export meldet sie einen Blocker; synthetische
Tests werden nicht als reale Marktabdeckung ausgegeben.

Der darauf aufbauende, vollständig lesende
[V2.5.2-Kandidatenscanner](docs/short-term-opportunities-v252.md) berechnet nachvollziehbare
technische Merkmale, Point-in-Time-Katalysatoren und nicht ausführbare Risikoszenarien. Sein
Ergebnis ist Research (`candidate_research`, `watch_only` oder `unavailable`), keine
Kaufempfehlung, Wahrscheinlichkeit oder historische Rendite.

Die [V2.6-Marktabdeckung](docs/first-usable-stock-scanner-v26.md) erweitert diesen Pfad in
deterministischen, quotengeschützten Seiten auf zunächst 100 reale US-Aktien. Sie dokumentiert
Korrekturfenster, archivweite Revisionen, den getrennten SPY-Benchmark und den weiterhin
geschlossenen offiziellen Kalender-Gate.

## MVP
- Python 3.12, FastAPI, PostgreSQL, SQLAlchemy/Alembic, pytest.
- Isolated Docker Compose stack alongside existing Immich; no changes to Immich resources.
- Modular CEX spot, DEX pool, stock and authorized community-data adapters.
- Early 5m/15m volume/liquidity acceleration and news catalysts.
- Point-in-time audit trail for candidates, rejection reasons and 1h/4h/24h outcomes.
- Paper trading only; no live order execution.
- Bitpanda availability, spreads and fees must be verified before actionable recommendations.
- Secrets outside source control; database private; dashboard local-only until authentication.

## First Codex task
Scaffold API, worker, DB migrations, a real public spot provider and fixture provider, candidate engine, read-only dashboard endpoints, Docker Compose, automated tests and deployment instructions. Validate historical DOOD/ZEREBRO cases only with timestamped historical evidence and without look-ahead bias.

## Phase 1: implementierter Umfang

- Lesende FastAPI mit HTML-Dashboard, OpenAPI unter `/docs`, Health und Readiness.
- Separater Scheduler/Worker; Binance-Spot-Marktdaten ohne API-Schlüssel und
  synthetischer Fixture-Anbieter für Offline-Tests.
- PostgreSQL 17, SQLAlchemy, Alembic-Migrationen; OHLCV-Historie, unveränderliche
  Auswertungen mit Ablehnungsgründen, Signale und protokollierte Scan-Durchläufe.
- Volumenspitzen auf abgeschlossenen 5m-/15m-Kerzen; keine Order-Funktionen.

Aktien-, DEX- und Community-Anbieter sind Erweiterungspunkte, noch keine realen
Integrationen. Nachrichten, Liquiditätsanalyse, Paper-Portfolio, Bitpanda-Prüfung
und Outcome-Berechnung folgen später. Die Outcome-Tabelle ist für 1h/4h/24h
vorbereitet, wird aber noch nicht befüllt. DOOD/ZEREBRO sind **nicht validiert**;
Fixture-Daten sind kein historischer Nachweis.

## Einrichtung auf Hetzner neben Immich

Voraussetzungen: Linux, Git, Docker Engine und Docker Compose v2 mit Unterstützung
für `service_completed_successfully`, mindestens etwa 2 GB freie RAM-Reserve und
ausreichend Plattenplatz. Vorher prüfen, ob diese Reserve neben Immich vorhanden
ist. Die vier Services haben jeweils maximal 512 MiB RAM und 0,5 CPU; die Limits
sind in `compose.yaml` anpassbar. Logdateien rotieren bei 3 × 10 MB je Service.

Das Projekt in ein eigenes Verzeichnis klonen, **nicht** in Immichs Compose-Datei
integrieren:

```bash
git clone https://github.com/herrwurz/aktien-chancen-scanner-v5.git
cd aktien-chancen-scanner-v5
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Den erzeugten Wert als `POSTGRES_PASSWORD` in `.env` eintragen. Keine
Exchange-Schlüssel hinzufügen: Der Anbieter nutzt ausschließlich öffentliche
Marktdaten. `.env` ist von Git und Docker-Build-Kontext ausgeschlossen.

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
curl --fail http://127.0.0.1:8066/api/ready
curl --fail http://127.0.0.1:8066/api/runs
```

Die Datenbank muss gesund sein, bevor der einmalige `migrate`-Service startet.
API und Worker starten erst nach erfolgreicher Migration. `migrate` darf danach
mit Exit-Code 0 beendet sein. Ein erster Scan erfolgt direkt beim Worker-Start.
Bei einem Anbieterfehler startet die Anwendung trotzdem; `/api/runs` zeigt
`partial` oder `failed` und die betroffenen Märkte. Nach erfolgreichem Start
beobachten, ob der Worker regelmäßig neue Durchläufe protokolliert.

Projektname: `chancen-scanner-v6`. Compose erzeugt ausschließlich die zugehörigen
Container, `chancen-scanner-v6_scanner_postgres` sowie die eigenen Netzwerke
`chancen-scanner-v6_backend`, `chancen-scanner-v6_web` und
`chancen-scanner-v6_egress`. Keine externen
Volumes/Netzwerke, kein Docker-Socket-Mount, keine festen Containernamen und keine
Immich-Ressourcen werden verwendet. PostgreSQL hat keinen Host-Port. Der Worker verwendet das Egress-Netzwerk für Marktdaten-Abfragen; die API
verwendet das separate Web-Netzwerk für die lokale Portfreigabe.

Die Oberfläche bindet ausschließlich an `127.0.0.1:8066`. Vom eigenen Rechner
aus per SSH-Tunnel öffnen:

```bash
ssh -N -L 8066:127.0.0.1:8066 benutzer@hetzner-server
```

Danach im Browser `http://127.0.0.1:8066` aufrufen. Bis Authentifizierung
implementiert ist, keinen öffentlichen Reverse-Proxy oder eine Bindung an
`0.0.0.0` hinzufügen. `DASHBOARD_PORT` in `.env` ändern, falls Port 8066 belegt ist.

## Konfiguration

Alle Werte werden über Umgebungsvariablen gesetzt. Listen sind JSON-Arrays; die
äußeren einfachen Anführungszeichen in `.env` erhalten das JSON.

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | erforderlich | Lokales DB-Passwort; bei Einrichtung erzeugen |
| `PROVIDER` | `binance_spot` | `binance_spot` oder synthetischer `fixture`-Modus |
| `SYMBOLS` | `'["BTCUSDT","ETHUSDT"]'` | 1–100 Spot-Symbole, Großbuchstaben/Ziffern |
| `INTERVALS` | `'["5m","15m"]'` | Unterstützte Zeitraster |
| `SCAN_SECONDS` | `60` | Pause nach einem Durchlauf, mindestens 10 Sekunden |
| `VOLUME_LOOKBACK` | `20` | Anzahl vorheriger Vergleichskerzen, 1–998 |
| `VOLUME_THRESHOLD` | `3` | Mindestfaktor gegenüber dem Mittelwert, größer als 1 |
| `MIN_QUOTE_VOLUME` | `100000` | Mindestumsatz der Zielkerze in Quote-Währung |
| `DASHBOARD_PORT` | `8066` | Lokaler Host-Port der Weboberfläche |

`MIN_QUOTE_VOLUME` ist kein EUR-/USD-normalisierter Liquiditätswert: Bei BTCUSDT
ist die Einheit USDT, bei einem Paar mit BTC als Quote-Währung BTC. Für Phase 1
USDT-Paare wählen oder den Grenzwert passend zur Quote-Währung konfigurieren.

Lokal außerhalb von Compose zusätzlich `DATABASE_URL` setzen, alternativ
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`. Compose setzt diese gezielt; ein Shell-`DATABASE_URL` wird
nicht automatisch in Container übernommen. URL-Passwörter müssen URL-kodiert sein;
die einzelnen POSTGRES-Variablen unterstützen Sonderzeichen ohne URL-Kodierung.

## Signalregeln und Zeitbezug

Standardmäßig gilt: Volumen der Zielkerze ≥ 3 × Mittelwert der **20 vorherigen**
Kerzen und Quote-Volumen ≥ 100000. Alle Vergleichskerzen müssen zum gleichen
Anbieter, Markt und Zeitraster gehören und lückenlos unmittelbar vor der
Zielkerze liegen. Unzureichende Historie, Lücken, Null-Basisvolumen und zu geringe
Umsätze erzeugen dokumentierte Ablehnungen.

Der Anbieter `https://data-api.binance.vision/api/v3/klines` benötigt keine
Authentifizierung. Binance-Zeitstempel werden zu UTC und exklusiven
Kerzenschlussgrenzen normalisiert. Offene Kerzen werden verworfen. Anfragen haben
15 Sekunden Timeout und höchstens drei Versuche bei Transportfehlern, HTTP 429
oder 5xx; `Retry-After` wird bis maximal 30 Sekunden berücksichtigt. HTTP 418 und
andere 4xx beenden die Anfrage ohne erneuten Versuch. Der Worker arbeitet die
kleine Watchlist sequentiell ab; das ist kein marktweiter Echtzeit-Scanner.

Bei jedem Abruf werden `VOLUME_LOOKBACK + 2` aktuelle Kerzen angefragt. Die
Historie wächst während des Betriebs; längere Ausfälle werden noch nicht durch
einen vollständigen Backfill geschlossen. Lücken führen zu Ablehnungen, bis
wieder genügend zusammenhängende Kerzen vorliegen. Systemuhr per NTP synchron
halten. Provider-Verfügbarkeit und regionale Beschränkungen hängen vom Standort ab.

`open_time`/`close_time` bezeichnen Marktereignisse, `observed_at` die erste lokale
Beobachtung und `evaluated_at` die tatsächliche Auswertung. Beim ersten Import
können auch vergangene Kerzen ein Signal erhalten; dieses wurde erst beim
Import erkannt und ist kein Beleg für eine frühere Live-Erkennung. Es werden
keine späteren Kerzen als Vergleichsdaten verwendet. Einzigartige Schlüssel
verhindern doppelte Kerzen/Entscheidungen. Daten und Entscheidungen werden beim
erneuten Import nicht überschrieben. Veränderte Detektorparameter erhalten
einen eigenen `detector_key`. Ein PostgreSQL Advisory Lock verhindert parallele
Worker-Scans derselben Datenbank. Schreibtransaktionen verwenden die sperrende
Verbindung und prüfen vor jedem Zugriff, ob diese die Sperre weiterhin besitzt;
ein Verbindungsverlust darf keinen ungesperrten Scan fortsetzen.

## API und Architektur

| Pfad | Inhalt |
| --- | --- |
| `/` | Dashboard mit Signalen und letzten Durchläufen, Aktualisierung alle 60 s |
| `/api/health` | Prozess-Liveness ohne Datenbankabhängigkeit |
| `/api/ready` | Verbindung und Existenz der Anwendungstabellen; sonst HTTP 503 |
| `/api/candles` | Historische OHLCV-Daten |
| `/api/evaluations` | Alle Entscheidungen einschließlich Ablehnungsgründen |
| `/api/signals` | Positive Volumenentscheidungen, immer `actionable=false` |
| `/api/runs` | Scan-Status und bereinigte Fehlerklassen je Markt |
| `/docs` | Interaktive API-Dokumentation |

Daten-Endpunkte sind ausschließlich GET. Kerzen und Entscheidungen unterstützen
`symbol`, `interval`, `provider`, `asset_class`, `limit` (1–500) und `offset`.
`/api/runs` unterstützt `limit` (1–100). Decimal-Messwerte werden als Strings
ausgegeben, damit Clients Präzision selbst kontrollieren können.

```text
scanner/domain.py          normalisierte UTC-/Decimal-Kerzen
scanner/providers/base.py gemeinsame Crypto-/Stock-Provider-Schnittstelle
scanner/providers/        öffentlicher Spot- und synthetischer Fixture-Anbieter
scanner/detector.py        unabhängige kausale Volumenentscheidung
scanner/models.py         Kerzen, Auswertungen, Signale, Outcomes, Scan-Läufe
scanner/service.py        transaktionaler Import und Fehlerisolation
scanner/worker.py         Scheduler und CLI (--once für einen Durchlauf)
scanner/main.py           lesende API und Jinja-Weboberfläche
migrations/               versioniertes Alembic-Schema
```

Ein neuer Aktienanbieter implementiert `MarketDataProvider` und liefert `Candle`
mit `asset_class="stock"`. Börsenkalender, Handelsunterbrechungen und typische
Aktien-Volumenprofile benötigen einen eigenen Detektor, bevor Aktien-Signale
aktiviert werden. Nicht-OHLCV-Daten wie Nachrichten erhalten eigene Domänen.

## Offline-Demo und lokale Entwicklung

Für einen Docker-Demo-Start `PROVIDER=fixture` in `.env` setzen und
`docker compose up -d` ausführen. Die Oberfläche kennzeichnet synthetische Daten.
Der Fixture-Anbieter spielt abgeschlossene Blöcke von 21 Kerzen ab und wechselt
erst zum nächsten vollständigen Block; pro Block liegt eine Volumenspitze vor.
Die Demo ist deshalb kein aktueller Live-Datenstrom. Gleiche Zeitstempel liefern
auch bei späteren Abrufen dieselben Werte.
Ein einmaliger Demo-Scan ist möglich mit:

```bash
docker compose run --rm --no-deps -e PROVIDER=fixture worker python -m scanner.worker --once
```

Dafür müssen Datenbank und Migration bereits bereit sein. Wenn ein laufender
Worker die Sperre hält, endet `--once` mit Exit-Code 1. Für einen Live-Durchlauf
`-e PROVIDER=fixture` weglassen.

Entwicklung mit Python 3.12:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
export DATABASE_URL='sqlite:///./development.db'
alembic upgrade head
PROVIDER=fixture python -m scanner.worker --once
uvicorn scanner.main:create_app --factory --host 127.0.0.1 --port 8066
```

SQLite ist ausschließlich eine lokale Test-/Demo-Option. PostgreSQL ist das
Produktionssystem; nur dort gilt die Worker-Sperre. Die vollständig gepinnten
Lockdateien enthalten Laufzeit- bzw. Testabhängigkeiten. Bei Updates beide
Lockdateien bewusst neu erzeugen und die gesamte Suite ausführen.

## Tests

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

Ohne `TEST_DATABASE_URL` werden die PostgreSQL-Integrationstests übersprungen.
Dieser Test führt **Upgrade, Downgrade, erneutes Upgrade und TRUNCATE** durch.
Nur eine leere, wegwerfbare Testdatenbank angeben, niemals die Betriebsdatenbank:

```bash
docker run -d --name scanner-test-postgres \
  -e POSTGRES_DB=scanner_test -e POSTGRES_USER=scanner \
  -e POSTGRES_PASSWORD=local-test-only \
  -p 127.0.0.1:55466:5432 postgres:17.6-bookworm
# Warten, bis pg_isready erfolgreich ist:
docker exec scanner-test-postgres pg_isready -U scanner -d scanner_test
TEST_DATABASE_URL='postgresql+psycopg://scanner:local-test-only@127.0.0.1:55466/scanner_test' \
  python -m pytest -q
docker rm -fv scanner-test-postgres
```

CI führt dieselbe Suite mit eigener PostgreSQL-Service-Datenbank, Ruff,
Compose-Konfigurationsprüfung und Docker-Build aus. Live-Marktdaten sind bewusst
kein deterministischer Bestandteil von pytest. Ausgeführte lokale Prüfungen:
[docs/test-results.md](docs/test-results.md).

## Betrieb, Sicherung und Updates

Nur aus diesem Projektverzeichnis arbeiten; keinen globalen Docker-Cleanup und
keine Immich-Compose-Befehle ausführen.

```bash
docker compose logs --tail=100 worker api migrate
docker compose exec -T db pg_dump -U scanner -d scanner -Fc > scanner-backup.dump
docker compose stop worker api
git pull --ff-only
docker compose build
docker compose run --rm migrate
docker compose up -d --wait
```

Backups enthalten Marktdaten und Entscheidungen; außerhalb des Servers sichern
und Wiederherstellung in einer separaten Testdatenbank prüfen. Für eine
Wiederherstellung zuerst API und Worker stoppen, dann in eine **leere** Datenbank
mit `pg_restore -U scanner -d scanner` importieren. Kein automatischer
Schema-Downgrade auf Betriebsdaten. Das DB-Passwort in `.env` nach der ersten
Initialisierung zu ändern ändert nicht das Passwort im vorhandenen Volume;
Passwortänderungen müssen zusätzlich in PostgreSQL durchgeführt werden.

`docker compose down` entfernt nur dieses Projekt und erhält sein Datenvolume.
`docker compose down -v` löscht die Scanner-Daten unwiederbringlich und gehört
nicht zum normalen Betrieb. Migrationen oder Anbieterfehler erscheinen in den
Service-Logs; Request-URLs, Payloads und Passwörter werden vom Worker nicht
protokolliert. Unfertige `running`-Einträge nach hartem Prozessabbruch bleiben
als solche sichtbar; der nächste Worker-Start beginnt einen neuen Durchlauf.

V1.6 verbindet die historischen Freigabeprüfungen mit einem Vier-Regeln-Aktienmodell:
[Auditablauf, Datenlücken und Backtest-Semantik](docs/hebeltrader-backtest-v16.md).
`historical-data audit --evaluate` bleibt schreibgeschützt und benötigt keine
Netzwerkverbindung; `historical-data verify` prüft die erzeugten JSON-/CSV-Pakete.

V1.7 ergänzt einen einzelnen Johnson-&-Johnson-Piloten ohne Datenbankänderungen:
[Originalabgleich, EODHD-Ablauf, Freigaben und Hetzner-Befehle](docs/hebeltrader-jnj-pilot-v17.md).
`python -m scanner.hebeltrader pilot run` erzeugt auch bei fehlenden Voraussetzungen
prüfbare Blocker; `pilot verify` prüft JSON/CSV/Markdown samt SHA-256.

Die V1.7-Ergänzung priorisiert den empfohlenen Call HS5RMP, ergänzt einen
unveränderlichen Bid/Ask-Importer und Tiingo als zweiten Basiswertprovider:
[HS5RMP-/Tiingo-Ablauf, Quellenprüfung und Offline-Abnahme](docs/hebeltrader-hs5rmp-tiingo-v17.md).

V2.2 ergänzt einen gemeinsamen, providerneutralen Aktien- und Ereignis-Recherchedienst.
Die [Anbieterentscheidung](docs/research-provider-decision.md) und der
[Betriebs- und Auditablauf](docs/research-v22.md) dokumentieren Kosten, Quellenrechte,
Zeitbezug, unveränderliche Caches und den aktuellen Live-Coverage-Blocker. Der Dienst
erzeugt Evidenz und Identitätsprüfungen, aber keine Kauf- oder Strategieentscheidung.

V2.3 verbindet den Detektiv explizit mit Fixture-, archivierter oder begrenzter Live-Recherche.
Der [Betriebs-, Quellen- und Abnahmebericht](docs/research-v23.md) beschreibt SEC-XBRL-Fakten,
GLEIF-Identitäten, Point-in-time-Grenzen und den realen Blindteaser-Versuch. Die Anwendung ist
wegen begrenzter Branchen- und internationaler Nachrichtenevidenz noch nicht allgemein für
unbekannte Teaser einsetzbar und liefert bei Mehrdeutigkeit `unresolved`.

Die V3.1-Webrecherche erhält blockierte Quellen über Tavily Extract beziehungsweise begrenzte,
archivierte Suchtreffer. Sie zeigt deren Quellenklasse und zeitliche Verwendbarkeit, gewichtet
spezifische Belege stärker und weist punktgleiche Spitzenkandidaten als Gleichstand aus.
