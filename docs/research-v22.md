# Gemeinsame Aktienrecherche V2.2

V2.2 ergänzt eine kontrollierte SEC-EDGAR-Datenquelle und normalisierte, strategieunabhängige
Research-Modelle. SEC-Ereignisse dürfen vom Detektiv sowie späteren Kurz- und Mittelfristmodulen
gelesen werden; kein Provider erzeugt Kauf-, Verkaufs- oder Trainingslabels.

## Offline und Dry Run

Alle Live-Zugriffe sind standardmäßig gesperrt. `SecEdgarClient` benötigt gleichzeitig
`allow_network=True`, ein positives Request-Limit und `SEC_USER_AGENT` im Format
`Anwendung kontakt@example.org`. `dry_run=True` beschreibt nur die geplante Anfrage.

Antworten werden nach Request-Schlüssel dedupliziert und als unveränderliche SHA-256-Rohdaten
gespeichert. 429/5xx und Transportfehler erhalten höchstens drei Versuche mit begrenztem Backoff.
Providerfehler erscheinen als `ProviderStatus(status="unavailable")`; es werden keine Ersatzdaten
erfunden.

Für den historischen Zeitbezug bleiben Abrufzeit und belegte Quellenverfügbarkeit getrennt. Bei
SEC-Filings ist `source_available_at` der Acceptance-Zeitpunkt der SEC; `retrieved_at` bezeichnet
den späteren Archivabruf. Der Detektiv darf ein Filing erst ab `source_available_at` verwenden und
schließt spätere Ereignisse aus. Quellen ohne belegte historische Verfügbarkeit verwenden
konservativ den tatsächlichen Abrufzeitpunkt.

Der schreibgeschützte CLI-Pfad erzeugt sortierte, maschinenlesbare JSON-Berichte. Ein Dry Run
benötigt weder Schlüssel noch Netzwerk:

```bash
python -m scanner.research_cli \
  --cache-dir reports/research-v22/sec-cache \
  --output reports/research-v22/dry-run.json \
  --dry-run sec-universe
```

Ein echter Abruf muss über `--allow-network --max-requests 1` begrenzt werden. Er benötigt einen
deklarierten `SEC_USER_AGENT`; der Abruf greift weiterhin weder auf PostgreSQL noch auf eine
Handelsfunktion zu. Bereits archivierte Antworten werden ohne Netzwerkanfrage aus dem anhand
SHA-256 geprüften Cache gelesen.

## Hetzner-Test ohne Deployment

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/shared-stock-research-v2-2
git switch --detach origin/feat/shared-stock-research-v2-2
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD muss gesetzt sein}"
docker compose build api
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD/reports:/reports" chancen-scanner-v6:local \
  python -m scanner.research_cli --cache-dir /tmp/sec \
  --output /reports/research-v22/dry-run.json --dry-run sec-universe
```

Der Befehl startet keine Compose-Dienste, greift nicht auf PostgreSQL zu und führt keine
Netzwerkanfrage aus.

## Reproduzierbare Abnahme

```bash
ruff check .
ruff format --check .
pytest tests/test_research_v22.py tests/hebeltrader/test_detective_mvp.py -q
pytest -q
POSTGRES_PASSWORD=compose-check-only docker compose config --quiet
docker build -t scanner-v22-check .
```

Der lokale V2.2-/Detektivlauf ergab `23 passed`; die übrige Suite ohne den in dieser
Entwicklungsumgebung hängenden FastAPI-TestClient-Test ergab `422 passed, 8 skipped`. Die
vollständige Suite mit PostgreSQL und der Docker-Build laufen in GitHub Actions. Das reale,
kostenlose SEC-Coverage-Protokoll steht in `research-v22-live-coverage.json`: 10.425 reale
US-Instrumentzeilen und 1.000 Filing-Ereignisse im Stichprobenabruf. Es belegt ausdrücklich keine
globale Blindidentifikation; dafür fehlen Branchen-, WKN-/ISIN- und allgemeine historische
Nachrichtenabdeckung.
