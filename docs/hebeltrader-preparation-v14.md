# HEBELTRADER Datenaufbereitung V1.4

V1.4 ergänzt die V1.3-Pipeline, ohne Importparser, Schema, gespeicherte Werte,
Identitätsfreigaben oder Backtest-Modi zu ändern. Alle Befehle sind manuell
aufzurufen. Kein Worker, Scanner, Trade, Deployment oder Datenbank-Upgrade nötig.

## Reproduzierbarer Offline-Export

Im bestehenden Python-/Analyse-Container sind dieselben Kommandos verwendbar.
`DATABASE_URL` ausschließlich sicher über die Umgebung setzen, niemals einchecken.
Für PostgreSQL wird jede Exporttransaktion explizit READ ONLY; für SQLite gilt
zusätzlich `query_only=ON`. Empfohlen ist ein eigener SELECT-only-Datenbanknutzer.

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
# Beispiel: bereits vorhandenes lokales Inventar strikt schreibgeschützt öffnen:
export DATABASE_URL='sqlite:///file:/absolute/inventory.db?mode=ro&uri=true'
python -m scanner.hebeltrader prepare \
  --run-at 2026-10-22T00:00:00+00:00 --expected-count 118 \
  --output-prefix /private/review/v14
```

Es entstehen acht neue Dateien: `.json`/`.csv` mit allen Empfehlungen,
`.rules.draft.json`, `.identity-input.json`, `.identities.json`/`.identities.csv`
und `.quality.json`/`.quality.csv`. Vorhandene Dateien werden niemals ersetzt.
Dateien erhalten Modus 0600, neu angelegte Elternordner 0700. Exporte enthalten
Originalzitate und gehören in einen privaten Ordner außerhalb des Repositorys.
CSV `record_json` enthält dieselben strukturierten Datensätze wie JSON, ohne
verlustbehaftete Zerlegung verschachtelter Quellen. Gleiche Eingaben und derselbe
`--run-at` ergeben bytegleiche Dateien. Der abschließende SHA bindet den gesamten
Report ohne sein eigenes Hashfeld (JSON sort_keys, ensure_ascii=False, default=str).
Abweichende Bestandszahlen führen nach dem Diagnoseexport zu Exitcode 2.

## Regelvorschläge und manuelle Freigabe

PDF-Bytes werden gegen Dokument-SHA geprüft. Empfehlungen sind mit SHA und Ordinal
gebunden. Zitate stammen ausschließlich aus gespeicherten Originalseiten oder
belegten Tabellenregionen. Seitenangaben, optionale Bounding-Boxen, heuristische
Konfidenz und Prüfhinweise bleiben erhalten. Volltexttreffer haben ausdrücklich
ungeprüften Dokumentbezug: mehrere Produkte/Spalten können eine manuelle
Zuordnung erfordern. Mehrdeutige Trigger, Negationen, widersprüchliche Regeln und
unklare Zeiteinheiten ergeben keine ausführbare Regel. Kein Standard-Teilverkauf,
Standardstopp oder Standardausstieg wird ergänzt. Anzahl der Treffer ist keine
Anzahl belastbarer Handelsregeln.

Entwürfe besitzen `review_status=pending`, `requires_manual_review=true` und keine
Reviewer-Freigabe. Der Backtest lehnt sie auch dann ab, wenn nur ein Reviewer
nachgetragen wird. Eine Person muss Originalseite, Aktien-/Derivatbezug, Auslöser,
Zeitbedingung und Vollständigkeit prüfen, eine separate rules.json erstellen,
`review_status=approved`/`requires_manual_review=false` setzen sowie Reviewer und
Zeitzonen-Zeitstempel ergänzen. Die bestehenden V1.3-Evidenzprüfungen bleiben
verbindlich; ältere vollständig dokumentierte Freigaben ohne neue Statusfelder
bleiben kompatibel. Der Assistent schreibt niemals bestehende rules.json.

## Historische Identitäten

Die 114 WKN-Vorkommen ergeben 96 unterschiedliche WKN. Der Offline-Export erzeugt
für diese ein dedupliziertes Recherchemanifest, aber keine erfundenen Kandidaten.
Optional ist ein ausdrücklich aktivierter öffentlicher OpenFIGI-Abruf möglich:

```sh
python -m scanner.hebeltrader identity-collect \
  --input /private/review/v14.identity-input.json \
  --output /private/review/openfigi.json --cache-dir /private/review/raw \
  --provider openfigi --allow-network
python -m scanner.hebeltrader prepare \
  --run-at 2026-10-23T00:00:00+00:00 --expected-count 118 \
  --identity-sources /private/review/openfigi.json --identity-cache /private/review/raw \
  --output-prefix /private/review/v14-with-candidates
```

Keine Schlüssel, kostenpflichtigen APIs oder Abonnements. Abruf ist standardmäßig
abgeschaltet; der Export selbst verwendet nie Netzwerkzugriff. Hashgebundene
Rohantworten werden unveränderlich gespeichert und beim Export erneut geprüft.
Die Abfragezuordnung beruht auf der Reihenfolge des Collector-Requests, da OpenFIGI
WKN nicht unabhängig zurückliefert. Hashintegrität beweist keine Quellenauthentizität.
Heutige OpenFIGI-Ticker sind ausdrücklich keine historischen Ticker. ISIN,
Börsenzeitzone, MIC, Währung, Listing-Gültigkeit und Delisting bleiben unbekannt,
wenn die Quelle sie nicht ausdrücklich belegt. Kein Kandidat wird ausgewählt,
`identity_status` bleibt immer `unverified`. Mehrere Kandidaten bleiben sichtbar.
Datiertes manuell gesammeltes Quellenmaterial kann als `historical_source` im
Schema des Moduls übergeben werden; Lizenz und konkrete Quellenreferenz sind
Pflicht. Auch das ist eine ungeprüfte Behauptung bis zur menschlichen Bestätigung.
Siehe [Quellen und Nutzungsrechte](hebeltrader-identity-v14-sources.md).

## Tatsächliches Ergebnis der 118er-Prüfung

Das bestehende lokale V1.3-Inventar wurde ausschließlich lesend ausgewertet.
[Aggregierter Bericht](hebeltrader-preparation-v14-baseline.json):

- 118/118 Empfehlungen inventarisiert und Original-SHA geprüft; alle besitzen
  zitierte Regel-/Zielhinweise, 28 besitzen mindestens ein unterstütztes
  Aktionsfeld im Entwurf. Das ist keine vollständige oder freigegebene Strategie.
- Alle 118 benötigen manuelle Regelprüfung; automatisch freigegeben: null.
- Vier fehlende Aktienkennungen, zwei fehlende Währungsbelege, zwei fehlende
  Stopp-1-, zwei fehlende Ziel-1- und drei fehlende Ziel-2-Werte sowie ein
  ungeprüfter Ziel-2-Wert liegen zusammen in fünf Dokumenten. Fehlend und
  ungeprüft können sich überlappen; die Prüfliste zählt den Befund nur einmal.
- Die Priorisierung beginnt mit Aktienkennung, Währungsbeleg, Stopp, Ziel1, Ziel2;
  ungeprüfte Konflikte erhalten innerhalb des Feldes Vorrang. Fehlende direkte
  Feldbelege erhalten ausdrücklich nur Seitenkontext, kein erfundenes Zitat.
- 114 WKN-Vorkommen/96 eindeutige WKN sind recherchebereit, null Identitäten
  verifiziert. Der öffentliche Testzugriff war in dieser Umgebung mit ConnectError
  nicht verfügbar; es wurden keine echten Kandidaten gesammelt. Offline-Tests
  verwenden ausdrücklich synthetische Quellen, keine historischen Behauptungen.
- Alle acht JSON-/CSV-Dateien wurden bei festem Replay-Zeitpunkt zweimal erzeugt
  und auf Bytegleichheit geprüft. Originaltexte bleiben außerhalb des Repositorys.

Für belastbare historische Backtests fehlen weiterhin manuell belegte historische
Listings/Identitäten, passende point-in-time OHLCV-Daten mit Kalender, Zeitzone,
Währung, Corporate Actions und Delistings sowie vollständige freigegebene Regeln.
Im strengen Modus bleibt zusätzlich verifizierte historische Verfügbarkeit nötig.
Der Forschungsmodus modelliert Verfügbarkeit weiter nur hypothetisch gemäß V1.2.
V1.4 bewertet keine Erfolge, berechnet keine Trainingslabels und liest keine
Verzeichnisnamen all/half/fail. Alle Exportempfehlungen: training_eligible=false.

## Validierung

```sh
ruff check .
ruff format --check .
python -m pytest -q
# Ohne Netzwerk/PostgreSQL gezielt:
python -m pytest tests/hebeltrader tests/test_identity_assistant.py -q
```

CI nutzt ausschließlich eine kurzlebige Test-PostgreSQL-Instanz. Keine Migration
oder Datenänderung an vorhandenen Umgebungen ist Bestandteil dieser Arbeit.
