# Prüfergebnisse – Phase 1

Ausgeführt am 21.10.2026 in einer isolierten Entwicklungsumgebung, nicht auf
dem Hetzner-/Immich-Server. Python 3.12.14 lokal, Python 3.12.12 im gebauten
Image; PostgreSQL 17.6 im separaten Testcontainer.

## Automatisierte Tests

```text
TEST_DATABASE_URL=<wegwerfbare PostgreSQL-Testdatenbank> python -m pytest -q
52 passed

ruff check .
All checks passed!

ruff format --check .
21 files already formatted

git diff --check
Exit 0

python -m pip check
No broken requirements found.

POSTGRES_PASSWORD=<Testwert> docker compose config --quiet
Exit 0
```

Enthaltene Prüfungen: UTC-/Decimal-/OHLC-Validierung, abgeschlossene Kerzen,
Volumenschwelle und Ablehnungsgründe, Zukunftsdaten und Lücken, begrenzte
Wiederholungen bei Rate-Limit/Timeout/5xx, HTTP 418 ohne Retry,
Retry-After-Begrenzung, unveränderte Fixture-Kerzen, idempotente Persistenz,
Rollback, Fehlerisolation je Symbol, genaue Beobachtungs-/Auswertungszeitpunkte,
lesende API mit Filtern/Pagination und DB-Readiness, Compose-Isolation.

Die PostgreSQL-Tests führen Alembic-Upgrade, Driftprüfung (`alembic check`),
Downgrade und erneutes Upgrade durch. Zusätzlich prüfen sie echte Persistenz,
konkurrierende Advisory Locks und den Verlust der Sperrverbindung durch
`pg_terminate_backend`: Der alte Worker darf anschließend nicht schreiben.
Ohne `TEST_DATABASE_URL` werden die beiden PostgreSQL-Tests übersprungen.

## Container- und Live-Prüfungen

- Docker-Build erfolgreich, optionales öffentliches CA-Bundle ausschließlich als
  BuildKit-Secret für den Entwicklungsproxy gemountet.
- Migration im Image als UID 10001 erfolgreich, auch mit lokaler SQLite-Testdatei.
- Vollständiger Compose-Start unter **`chancen-scanner-v6-phase1-smoke`**:
  DB und API gesund, Migration Exit 0, Worker aktiv mit `status=ok`.
- Dashboard und alle sieben geprüften HTTP-Routen antworten über
  `127.0.0.1:18066` mit HTTP 200. Dashboard kennzeichnet Fixture-Daten;
  Signal-Antworten enthalten `actionable=false`.
- Öffentlicher Binance-Spot-Abruf: 21 abgeschlossene BTCUSDT-5m-Kerzen empfangen.
- Zusätzlicher echter Container-Worker mit `--once`: BTCUSDT und ETHUSDT,
  jeweils 5m/15m, vier HTTP-200-Antworten, Persistenz in der eigenen
  Smoke-Datenbank, `Scan finished: ok`, Exit 0. Keine API-Schlüssel verwendet.

Beim ersten Container-Test gefundene Fehler wurden vor Abschluss behoben:
Dateieigentümer für den nicht privilegierten Benutzer und ein separates
Web-Netzwerk für die lokale Portfreigabe. Die vollständige Start-/HTTP-Prüfung
wurde danach erfolgreich wiederholt.

## Codeprüfung und Grenzen

Eine unabhängige, lesende Prüfung der Implementierung fand zwei relevante
Probleme: zurückdatierte Audit-Zeitpunkte und eine getrennte Sperrverbindung,
deren Verlust parallele Worker ermöglichen konnte. Beide wurden mit zunächst
fehlschlagenden Regressionstests reproduziert und korrigiert. Auch der Hinweis
auf inkonsistente Fixture-Werte wurde behoben; zusätzliche Retry-Grenzfälle
sind getestet. Keine offenen wesentlichen Review-Befunde.

Nicht geprüft oder behauptet: Deployment auf Hetzner, historische
DOOD-/ZEREBRO-Validierung, Performance eines Gesamtmarkt-Scans, Aktien-/DEX-Daten,
Bitpanda-Handelbarkeit oder berechnete 1h/4h/24h-Outcomes. GitHub Actions ist
eingerichtet; der tatsächliche CI-Status ist am Pull Request abzulesen.
