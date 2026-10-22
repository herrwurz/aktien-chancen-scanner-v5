# HEBELTRADER V1.6: prüfbare Aktienmodelle

V1.6 baut auf PR #11/V1.5 auf. Datenbank und Original-PDFs werden nur gelesen.
Es gibt keine Migration, automatische Freigabe, Orders, Live-Signale oder
Installation auf Hetzner. Das bestehende V1.5-Audit bleibt ohne `--evaluate`
verfügbar; alte Regeln werden im neuen Modell ausdrücklich als unvollständig
behandelt. Kein Verzeichnisname (`all`, `half`, `fail`) wird zum Erfolgslabel.

## Tatsächlich verfügbare Daten

Der lokale Originalbestand enthält 118 Empfehlungen, 114 Aktien-WKN-Vorkommen,
96 unterschiedliche WKN und vier fehlende Aktienkennungen. Die veröffentlichte
[Coverage-Matrix](hebeltrader-backtest-v16-matrix.csv) enthält alle 118
SHA-/Ordinal-Schlüssel ohne PDF-Volltexte. Die zugehörige
[Baseline](hebeltrader-backtest-v16-baseline.json) unterscheidet Messungen von
extern berichteten Zahlen. Alle 118 Original-SHAs sind gültig.

Die echten drei OpenFIGI-Exporte einschließlich Rohantworten liegen ausschließlich
auf Hetzner und wurden hier **nicht** eingelesen. 94 Treffer sind eine vom Nutzer
berichtete Zahl, keine lokale Messung und kein historischer Identitätsnachweis.
Hier wurden keine EODHD-Anfragen ausgeführt und keine Abonnements aktiviert.
Die lokale Eingangsprüfung kann daher keine vollständige historische Identität,
Kursreihe oder Vier-Regeln-Freigabe bestätigen. Null lokal auswertbare Fälle
bedeutet nicht, dass die Aktien beim Anbieter nicht abgedeckt sind. Die tatsächliche
externe Coverage muss mit den echten Dateien gemessen werden.

## Schreibgeschützter Import vorhandener OpenFIGI-Dateien

Der Import ist eine flüchtige Verknüpfung mit dem Datenbankinventar und ein neues
Auditpaket; er schreibt keine Kandidaten in die Datenbank. PostgreSQL-Zugang mit
SELECT-Rechten verwenden; das Kommando setzt zusätzlich `SET TRANSACTION READ ONLY`.
Für SQLite wird `PRAGMA query_only=ON` gesetzt. Keine `alembic`- oder Importpipeline
starten. `DATABASE_URL` ausschließlich über sichere Umgebung bereitstellen.

Beispiel für einen später separat ausgeführten Serverlauf (hier nicht ausgeführt):

```bash
python -m scanner.hebeltrader historical-data audit \
  --evaluate \
  --openfigi reports/hebeltrader/preparation-v14/openfigi.json \
  --openfigi-cache reports/hebeltrader/preparation-v14/openfigi-raw \
  --linked-identities reports/hebeltrader/preparation-v14/preparation-openfigi.identities.json \
  --run-at 2026-10-22T12:00:00+00:00 \
  --as-of 2026-10-22T00:00:00+00:00 \
  --expected-count 118 \
  --output-prefix reports/hebeltrader/backtest-v16/run-001
python -m scanner.hebeltrader historical-data verify \
  --output-prefix reports/hebeltrader/backtest-v16/run-001
```

Das Audit prüft Originalexport-SHA, Rohantwort-SHA, JSON-Pointer,
Kandidatenübereinstimmung und Inventar des verknüpften Exports. Mehrere Börsenplätze
bleiben getrennte Kandidaten. Abweichungen blockieren V1.6-Auswertungen.
Ein `verified` im verknüpften Kandidatenexport wird nicht als Freigabe übernommen.
Es werden keine neuen OpenFIGI-Anfragen erzwungen. Bereits vorhandene Ausgabedateien
werden niemals überschrieben; für Wiederholung einen neuen Präfix wählen.

Die Ausgabe besteht aus JSON/CSV für Empfehlungen und Identitäten sowie einer
`.sha256.json` für alle vier Dateien. `verify` prüft SHA-256 und JSON-/CSV-Gleichheit.
Mit gleichen Eingaben, Zeitparametern und Datenbankstand sind alle Bytes identisch.
SHA-256 erkennt Veränderungen, ersetzt aber keine Signatur oder manipulationssichere
externe Archivierung. Auditdateien enthalten Zitate und gehören in ein geschütztes
Verzeichnis, nicht automatisch in öffentliche Repositories.

## Historische Identität und Datenbeschaffung

V1.5-Freigaben bleiben zwingend: WKN, ISIN, historischer Ticker, MIC, Börsenzeitzone,
Währung und Gültigkeitsintervall müssen durch gespeicherte, gehashte Quellenfelder
belegt sein. `--historical-sources`, `--map`, `--rules`, `--bundles`, `--data-root`
und `--eodhd-cache` ergänzen obigen Aufruf; Formate und Sammel-/Normalisierungsbefehle
stehen in [V1.5](hebeltrader-historical-v15.md). Reviewer, Freigabezeitpunkt und
Quellenbelege werden mit ausgegeben. Währung wird gegen PDF-Belege geprüft.
Heutige OpenFIGI-Kandidaten bestätigen keine historische Verfügbarkeit.

Fresenius 578560 benötigt die zeitlich passende Identität; der Wechsel zu FRE5EN
im August 2026 darf nicht stillschweigend auf ältere Empfehlungen übertragen werden.
Siehe [Quellen und V1.5-Prüfung](hebeltrader-historical-v15.md).
SJ6B4A bleibt wegen der Aktien-/Derivat-WKN-Kollision gesperrt. Eine vermutete
Daimler-Truck-Kennung wird nicht automatisch eingesetzt. Börsenplatzmehrdeutigkeit,
Delisting und Kennungswechsel brauchen jeweils datierte Quellen und manuelle Prüfung.

EODHD bleibt optional und nur mit separater Freigabe nutzbar. Der Collector benötigt
`EODHD_API_TOKEN` aus der Umgebung, `--allow-network`,
`--authorize-provider-usage`, positive `--max-requests` und ggf. `--max-api-units`.
`--monthly-total-eur` deklariert das gesamte externe Monatsbudget (maximal 100 EUR);
das ist keine Rechnungsüberwachung und keine Zustimmung zu einem Kauf. Preise,
Nutzungsrechte, Lizenz und API-Gewichte vor Nutzung beim Anbieter prüfen.
Keine kostenpflichtige Abfrage ist Teil der hier ausgeführten Tests.

Neu protokolliert `collect` Start, Erfolg/Fehler, angefragte Endpunkte, Zeitfenster,
Sammlungsschlüssel, Cache-Nutzung, Requestversuche und API-Einheiten in
`CACHE/usage.jsonl`. Eine gesperrte, append-only SHA-Kette prüft vor jedem Anhängen
den bisherigen Inhalt. Fehlerklassen statt authentifizierter URLs werden gespeichert.
`cost_eur=null` heißt unbekannte Rechnungskosten, ausdrücklich nicht kostenlos.
Ein beschädigtes Journal stoppt die Sammlung vor weiteren API-Aufrufen.
Ein Prozessabbruch hinterlässt ggf. einen Start ohne Abschluss; diesen Lauf prüfen,
keine Nullkosten annehmen. Anbieterquoten gelten zusätzlich zu lokalen Limits.

Rohantworten und Manifeste bleiben unveränderlich und werden vor Wiederverwendung
gehasht. Normalisierung verlangt einen unabhängig belegten Handelskalender und
vergleicht OHLCV mit tatsächlichen Sitzungen (inklusive verkürzter Tage/Zeitzonen).
Splits, Dividenden und Delisting-Angaben werden erhalten. Nicht freigegebene
Corporate-Action-Behandlung, Lücken oder Identitätswechsel blockieren die Auswertung;
es gibt kein stilles Auffüllen, keine Adjusted-Close-Substitution und kein
Durchrechnen über ungeklärte Splits. Das Modell ist eine Brutto-Aktienpreisrechnung,
keine Total-Return-Rechnung mit erfundenen Dividenden-Cashflows.

## Vier freigegebene Regeltypen

V1.6 wird mit `rule_version: "1.6"` explizit aktiviert. Beispiel einer **synthetischen
Struktur**, kein Vorschlag zur automatischen Freigabe eines echten Dokuments:

```json
{
  "rule_version": "1.6",
  "document_sha": "<Original-SHA-256>",
  "ordinal": 1,
  "instrument_scope": "stock",
  "review_status": "approved",
  "requires_manual_review": false,
  "reviewer": "<menschlicher Reviewer>",
  "reviewed_at": "2026-10-22T10:00:00+00:00",
  "partial_fraction": 0.5,
  "after_target1": "entry",
  "target2_sale": {"fraction": 0.5, "trigger": "target2"},
  "conditional_loss_exit": {
    "days": 20,
    "unit": "calendar_days",
    "condition": "position_in_loss",
    "threshold": "at_least",
    "loss_basis": "total_position",
    "evaluation": "completed_close",
    "execution": "next_session_open"
  },
  "evidence": [
    {"page": 3, "region": 0, "quote": "<wörtlicher Originaltext>",
     "fields": ["partial_fraction", "after_target1", "target2_sale", "conditional_loss_exit"]}
  ]
}
```

Jeder der vier Typen braucht einen Original-Seitenbeleg. `region` ist optional und
bezeichnet den nullbasierten Index der gespeicherten Spaltenregion. Zitate werden
gegen Seite/Region geprüft, Dokument-SHA und Ordinal bleiben unverändert.
Manuelle Freigabe muss ausdrücklich den Aktienmodell-Geltungsbereich bestätigen;
eine Optionsscheinregel wird nicht unbemerkt auf die Aktie übertragen.
Die Regeln werden aus einer neuen Sidecar-Datei gelesen, niemals in Originaldaten
zurückgeschrieben. Ungeprüfte Extraktionsvorschläge reichen nicht.

`after_target1` unterstützt `entry`, `stop2`, `target1` oder ausdrücklich
`unchanged`. Bei Ziel 1 werden 50% verkauft, bei Ziel 2 die verbleibenden 50%.
`loss_basis` muss ausdrücklich zwischen Verlust der Gesamtposition
(inklusive Teilverkaufserlös) und Verlust nur des Restbestands unterscheiden.

`trading_sessions`: Einstiegssitzung zählt als Sitzung 1; die 20. vollständige
Sitzung kann ein Signal auslösen. `calendar_days`: Datumsabstand in Börsenlokalzeit,
Einstiegstag zählt 0; Wochenenden zählen mit. Geprüft wird erst am vollständigen
Schlusskurs, **nur bei Verlust**. Ausführung frühestens zur nächsten vorhandenen
Sitzungseröffnung; selbst bei Erholung über Nacht bleibt das zuvor gebildete
Signal bestehen. Ohne nächste abgeschlossene Sitzung bleibt der Fall zensiert.

Nennt der Originaltext nur „Tage“, wird keine Einheit geraten: Ohne dokumentierte
`time_unit_interpretation` wird abgewiesen. Mit expliziter Interpretation gilt sie
als Forschungsannahme und blockiert den verifizierten Modus. Kein pauschaler
Verkauf nach 20 Tagen; alte unbedingte `exit_after`-Regeln sind kein Ersatz.

## Modell, Ereignisse und Kennzahlen

Forschungsmodus behält V1.2 bei: frühestens erste vollständige Handelssitzung nach
dem belegten Veröffentlichungstag, keine Behauptung tatsächlicher Verfügbarkeit.
Der verifizierte Modus verlangt zusätzlich die unverändert strengen historischen
Verfügbarkeitsnachweise. Beide Modi prüfen Identität, Kursdaten und vier Regeln.
Alle Ergebnisse bleiben hypothetisch, `training_eligible=false`; es gibt keine
automatisch bestätigten historischen Erfolge.

Einstieg ist die erste zulässige vollständige Sitzungseröffnung. Ziele werden
konservativ zum Limitpreis, Stopp-Lücken zum schlechteren Eröffnungskurs modelliert.
Bei gleichzeitigem Stopp und Ziel innerhalb einer Tageskerze gilt Stopp zuerst.
Auch die mögliche Berührung eines neu angehobenen Stopps in derselben Kerze ist
mehrdeutig. Solche Fälle liefern ausschließlich `conservative_return_pct`,
`status=ambiguous`, niemals eine eindeutige Rendite oder `fully_evaluable=true`.

Ereignisse enthalten Preis, Anteil, Sitzungsnummer, Kalenderabstand und Zeitintervall;
intrabar wird kein genauer Ausführungszeitpunkt behauptet. Kennzahlen enthalten
modellierte Ziel-/Stoppereignisse und anfängliches CRV für Ziel 1/2. Der ausgewiesene
Drawdown ist der beobachtete Rückgang der modellierten Position an vollständigen
Schlusskursen und bekannten Ausführungspunkten. Das echte maximale Intraday-Drawdown
ist aus Tageskerzen nicht eindeutig bestimmbar und bleibt `null`.
Offene Positionen und ausstehende Verlustausstiege erhalten keine erfundene
Schlussrendite. Die Quote vollständig auswertbarer Fälle verwendet alle 118 als
Nenner; unklare Fälle werden separat gezählt.

Für einen ersten belastbaren Aktienmodelllauf fehlen lokal: echte Exportdateien,
quellenbelegte historische Freigaben, autorisiert bezogene Kurs-/Corporate-Action-
Daten und Kalender, vollständige Regelprüfung inklusive Tages-/Verlustdefinition
sowie die übrigen PDF-Pflichtfeldkorrekturen. Für einen Optionsschein-Backtest fehlen
weiterhin historische Produktbedingungen, Bid/Ask, ausführbare Liquidität, Kosten
und ein eigenes Ausführungsmodell. Aktien-OHLCV ersetzt diese Daten niemals.

## Prüfungen

```bash
ruff check .
ruff format --check .
python -m pytest -q
POSTGRES_PASSWORD='<nur-lokales-Testpasswort>' docker compose --profile analysis config --quiet
docker build -t scanner-v16-check .
```

Tests verwenden markierte synthetische Daten, einschließlich eines festen
118er-Inventars mit 96 WKN. Daneben wurde der echte lokale 118er-Bestand mit
schreibgeschützter SQLite-Verbindung inventarisiert und reproduziert. Vollständige
Test-/CI-Ergebnisse werden im Pull Request dokumentiert. Docker und PostgreSQL
werden in der bestehenden GitHub-Actions-Pipeline separat geprüft; keine
Produktionsdatenbank oder bestehende Docker-Instanz wird dafür angesprochen.

### Lokale V1.6-Abnahme

Der lokale Modul-/Identitätslauf bestand mit 198 erfolgreichen Tests und fünf
übersprungenen PostgreSQL-Tests (kein lokaler Testserver). Ruff, Formatprüfung,
`git diff --check` und Compose-Konfiguration bestanden. Der vollständige lokale
pytest-Lauf wurde nach 35 Sekunden im Bereich der HTTP/TestClient-Tests mit Timeout
beendet; daraus wird kein vollständiger lokaler Erfolg abgeleitet.
Docker-Build wurde versucht, ist hier durch schreibgeschützte Docker-Konfiguration
und gesperrten Daemon nicht ausführbar. Maßgeblich für vollständige pytest-,
PostgreSQL- und Docker-Abnahme sind die zum PR verlinkten GitHub-Actions-Läufe.

Zwei echte lokale Inventarläufe mit identischen Zeitparametern lieferten identische
JSON-/CSV-/Hashdateien; die SQLite-Datei hatte davor und danach denselben SHA-256
(siehe Baseline). Der private Vollbericht liegt außerhalb des Repositories unter
`/workspace/artifacts/hebel-backtest-v16/final.*`. Die öffentliche Matrix ist eine
Projektion von `results` auf SHA, Ordinal, Publikationsdatum, Aktienname/-WKN/-Währung,
beide Modusfreigaben, Backteststatus und Blocker. Sie enthält keine PDF-Volltexte.
`source_report_sha256` bindet die Baseline an den vollständigen Ausgangsbericht;
`matrix_sha256` bindet sie an die öffentliche CSV. Die fünf bekannten Problem-SHAs
werden als Inventarregression geprüft; hier wird keiner davon ohne zusätzliche
Originalbelege als gelöst bezeichnet.
