# HEBELTRADER-Detektiv MVP

## Abgrenzung

Meilenstein 1 nimmt Teasertext und optional einen Screenshot entgegen und erstellt eine
reproduzierbare Kandidatenrangliste. Er recherchiert nicht live, erteilt keine Kaufempfehlung und
bestätigt kein Wertpapier ohne Quellenbeleg. Trading- und Investment-Scanner bleiben eigenständige
spätere Meilensteine.

## Datenfluss

```text
Text -------------------------+
                              +--> Hinweisextraktion --> Kandidaten-Ranking --> Audit-Ergebnis
Screenshot --> OCR-Adapter ---+                              |
                                                             +--> Call-Kandidaten (nur Katalog)
```

`scanner/hebeltrader/detective/` enthält:

- `ocr.py`: begrenzte Bildvalidierung und austauschbarer Tesseract-Adapter.
- `clues.py`: deterministische Extraktion von Kennungen, Zahlen und Textbegriffen.
- `sources.py`: austauschbare Verträge für Kandidaten- und Nachrichtenevidenz.
- `catalog.py`: sechs synthetische, datierte Offline-Fixtures mit klar begrenzter Abdeckung.
- `service.py`: gewichtetes Ranking, Unsicherheiten und vollständige Ergebnisstruktur.
- `schemas.py`: validierte API-Ein- und Ausgaben.
- `scanner/research.py`: gemeinsames Asset-/Evidenzmodell für spätere unabhängige Scanner.

Die API `POST /api/hebeltrader/detective/analyze` akzeptiert JSON mit `teaser_text`, optionalem
Base64-Bild, MIME-Typ und Veröffentlichungszeit. `/hebeltrader` bietet eine mobile Eingabemaske.
Das Ergebnis bleibt stateless; produktive Datenbanken und historische Originaldaten werden nicht
verändert.

## Qualitäts- und Sicherheitsgrenzen

- OCR ist eine Eingabequelle, kein Beleg. OCR-Fehler werden als Prüfhinweis ausgegeben.
- Evidenz enthält `source_id`, URL, `published_at`, `retrieved_at`, `effective_at` und SHA-256.
  Spätere oder erst später abgerufene Quellen werden aus historischen Vergleichen ausgeschlossen.
- Offline-Fixtures sind ausdrücklich synthetisch. Sie testen die Pipeline, keine reale Trefferquote.
- Das Ranking trennt harte Kennungen, unterstützende strukturierte Hinweise, Gegenbelege und
  nicht abgedeckte Hinweise. Relevanzwerte sind weder Wahrscheinlichkeiten noch kalibriert.
- Bei fehlender Evidenz, engem Rangabstand oder Titeln außerhalb des Universums wird `unresolved`
  ausgegeben.
- Die Rangfolge verwendet ausschließlich Eingaben und zum angegebenen Zeitpunkt verfügbare
  Katalogeinträge. Spätere Nachrichten werden im MVP nicht ergänzt.
- Ein Call wird nur als Kandidat ausgegeben. `confirmed=false` bleibt gesetzt, solange offizielle
  Produktunterlagen nicht manuell bestätigt wurden. Ohne explizite Derivate-WKN wird kein historisch
  verknüpftes Produkt als identifiziert ausgegeben.
- Bilder sind auf PNG/JPEG/WebP, zwei MiB und eine begrenzte Pixelzahl beschränkt. Tesseract läuft
  lokal ohne Netzwerk und mit Zeitlimit.

## Offline-Test und Hetzner

```bash
python -m pytest tests/hebeltrader/test_detective_mvp.py -q
PROVIDER=fixture uvicorn scanner.main:create_app --factory --host 127.0.0.1 --port 8066
```

Auf Hetzner nach Review des PR, ohne bestehende Dienste zu verändern:

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/hebeltrader-detective-mvp
git switch --detach origin/feat/hebeltrader-detective-mvp
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD muss gesetzt sein}"
docker compose build api
mkdir -p reports/hebeltrader
docker compose run --rm --no-deps --network none \
  -v "$PWD/docs/hebeltrader-detective-example.json:/input/example.json:ro" \
  -v "$PWD/reports/hebeltrader:/reports" api sh -c \
  'python -c "import json; p=json.load(open(\"/input/example.json\")); open(\"/tmp/teaser.txt\",\"w\").write(p[\"teaser_text\"])" && \
   python -m scanner.hebeltrader.detective.cli --text-file /tmp/teaser.txt \
   --publication-at 2025-08-05T08:15:00+02:00 --output /reports/detective-mvp.json'
```

Der Lauf verwendet nur das kontrollierte Beispiel, startet keine dauerhaften Dienste und benötigt
weder Datenbank noch Netzwerk. Es erfolgt kein Deployment durch diesen PR.

## Datenabdeckung und externer Blocker

Der Fixture-Adapter umfasst sechs Aktien aus Deutschland und den USA. Er dient ausschließlich den
Blind-, Mehrdeutigkeits-, Lookahead- und Out-of-Universe-Regressionen. Für echten allgemeinen
Betrieb fehlt eine budgetkompatible, lizenzrechtlich zulässige Quelle mit historischem
Publikations- und Verfügbarkeitszeitpunkt für Unternehmensidentitäten, Nachrichten, Kennzahlen und
Optionsschein-Stammdaten. Kostenpflichtige APIs werden nicht automatisch aktiviert. Bis eine solche
Quelle ausdrücklich konfiguriert und geprüft ist, muss die Anwendung bei fehlender datierter
Evidenz enthalten.
