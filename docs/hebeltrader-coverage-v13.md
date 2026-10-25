# Coverage-Audit und historische Marktdaten V1.3

Issue #7. **Status: erledigt** (PR #8; Identitäts-/Provider-Folgearbeit in V1.4–V1.6). GitHub-Issue kann geschlossen werden. V1.3 ergänzt Backtesting V1.2 um eine **reine Offline-Inventur** und
versionierte lokale Marktdaten. Keine neue Migration, kein Worker oder
Netzwerk-Download, kein Schreibzugriff auf Betriebsdaten, kein Trading.
`training_eligible` bleibt immer false; `success_rate` bleibt null.

## Ein Lauf für alle Empfehlungen

Mit vorhandener sicherer Datenbankkonfiguration, ohne Dateien umzubenennen
oder alte Importe zu verändern:

```bash
python -m scanner.hebeltrader coverage \
  --as-of 2026-10-22T00:00:00+02:00 \
  --run-at 2026-10-22T00:00:00+02:00 \
  --output-prefix /reports/coverage-v13
# Optional, sobald entsprechende lokale Nachweise vorhanden sind:
python -m scanner.hebeltrader coverage \
  --as-of 2026-10-22T00:00:00+02:00 \
  --bars-dir /input/market --map /input/mapping.json --rules /input/rules.json \
  --output-prefix /reports/coverage-v13-with-inputs
```

Ein Aufruf erzeugt `.json` und `.csv` am expliziten Prefix, neu mit Modus 0600.
Vorhandene Dateien/Symlinks werden niemals überschrieben. Ist ein Ziel bereits
vorhanden, wird kein unvollständiges neues Reportpaar zurückgelassen. Die
Dateien sind nach abgeschlossenem Lauf konsistent; zwei getrennte Dateipfade
können keine transaktionale Sicht für gleichzeitig lesende Fremdprozesse bieten.
CSV enthält die vollständige JSON-Zeile unter `record_json`; globale Prüfliste
und Zusammenfassung stehen im JSON. Reports können Originalzitate enthalten
und gehören in private Verzeichnisse, nicht ungeprüft ins öffentliche Git.

Default `--expected-count 118`; bei anderer Anzahl wird der vollständige Bericht
mit Warnung geschrieben und Code 2 zurückgegeben. Code 0 bedeutet passende
Inventur, **nicht vollständige Kursdaten oder Erfolg**. Für Testbestände Anzahl
explizit angeben. `--run-at` fixiert die Replay-Uhr für bytegleiche Wiederholung;
ohne Flag wird die aktuelle UTC-Zeit dokumentiert. `--as-of` und Replay-Uhr
brauchen Offsets, der Beobachtungsstichtag darf nicht nach der Replay-Uhr liegen.
Eingabestand, Stichtag und Replay-Uhr für echte Reproduktion zusammen archivieren.

Alle Empfehlungen bleiben über Dokument-SHA + Ordinal erhalten, auch bei
wiederholter WKN. DB-IDs sind zusätzlich enthalten, können aber zwischen
Datenbanken variieren. Der Befehl verwendet nur SELECT und PostgreSQL
`SET TRANSACTION READ ONLY`, ohne Commit/Autoflush. Kein Provider ruft ein
Netzwerk auf. Archivordner und PDF-Dateinamen werden nicht abgefragt.

## Unabhängige Stufen und Mehrfachblockaden

| Stufe | Bedingung |
|---|---|
| `publication_evidenced` | Passender Originalheader/Seitenbeleg und korrekter Original-SHA |
| `verified_availability` | Bestehende strenge V1.2-Verfügbarkeitsprüfung |
| `instrument_identity_verified` | Eindeutige zeitlich passende, manuell bestätigte Börsenplatz-Zuordnung |
| `rules_documented` | Dokument-/Ordinal-gebundene, belegte und manuell geprüfte Regeln |
| `market_history_sufficient` | Vollständige Kandidaten-Historie mit Kalender, Actions und Quellenmetadaten |
| `modeled_entry_executable` | Zulässige hypothetische Sitzung, bestätigte Identität und passende belegte Preisbasis |
| `derivative_bid_ask_verified` | Derzeit immer unvollständig: kein echter historischer Bid/Ask-Provider |

Jede Stufe zeigt eigene Gründe; nicht nur die erste Blockade. Regeln können
belegt sein, obwohl Marktdaten fehlen. Kandidaten-Historien können vollständig
sein, obwohl deren Identitätszuordnung noch ungeprüft ist. Das ist ausdrücklich
keine Identitätsbestätigung. Die Entry-Stufe benötigt dagegen eine bestätigte
Identität sowie belegte Währung und Ziele/Stopps aus der Empfehlung; die
Mapping-Währung ersetzt niemals fehlende Währungsevidenz der PDF-Preise.
Exit-Regeln sind für spätere Outcomes nötig, blockieren aber nicht die separate
Inventur der anfänglichen Einstiegsmöglichkeit.

`--analysis-mode research` ist die Audit-Voreinstellung für die hypothetische
Entry-Prüfung; `verified` bleibt optional streng. Beide ändern keine gespeicherte
Availability. V1.2-Kalender-, Zeit-, Revisions- und Lookahead-Regeln gelten weiter.
Gaps/Feiertage, fehlende Bars, stale/future Metadaten, Splits/Dividenden,
Währungswechsel und Delistings werden von den vorhandenen OHLCV-Prüfungen
konservativ behandelt. Auch bei vollständiger Modellabdeckung wird keine
Ausführung oder reale Rendite bestätigt.

`manual_review` ist stabil nach Stufenpriorität, SHA/Ordinal und Grund sortiert.
Sie listet alle Stufenblockaden, während `quality_flags` zusätzlich die
unveränderten bisherigen Dokument-/Extraktionshinweise trägt. Die Reihenfolge
ist ein Arbeitsplan, keine statistische Chancenbewertung. Fehlende Einzelpreise
und Identifikatoren werden auch ohne Mapping/Kursdateien einzeln sichtbar.

## Historische Instrumentauflösung

`identity.HistoricalIdentityProvider` trennt Identitätsauflösung von
`HistoricalStockProvider` und Preislieferung. Der vorhandene
`LocalIdentityProvider` nimmt lokale Vorschläge im Mapping entgegen. Schlüssel:
Aktien-WKN oder ISIN. Ein Wert kann ein einzelnes CSV-Spec oder eine Liste
mehrerer historischer Listings sein. Vorschläge bleiben **unverified**.

Für Auswahl zusätzlich zu den bisherigen Börsen-/Quellenfeldern erforderlich:

```json
{
  "identity_status": "verified",
  "identity_reference": "referenzierter historischer Instrumentnachweis",
  "identity_evidence": "nachgeprüfte WKN/ISIN-, Listing- und Währungszuordnung",
  "identity_reviewed_by": "Name des Prüfers",
  "identity_reviewed_at": "2026-10-22T00:00:00+02:00",
  "identity_valid_from": "2025-01-01T00:00:00+01:00",
  "identity_valid_until": "2026-10-22T00:00:00+02:00"
}
```

Diese Beispielwerte sind Schema-Erklärung, **keine tatsächliche Bestätigung**.
Symbol, Venue, IANA-Zeitzone, Währung und raw-Adjustierung bleiben erforderlich.
Die Geltung muss den gesamten Prüfzeitraum einschließen; Prüfzeiten nach der
Replay-Uhr werden abgewiesen. Fehlende ISIN verhindert eine belegte eindeutige
WKN-Zuordnung nicht. Mehrere gültige Listings/Handelsplätze/Währungen erzeugen
`identity_ambiguous`; es wird kein bevorzugter aktueller Ticker geraten.
Historische Umbenennungen dürfen getrennte zeitlich begrenzte Einträge haben.
Delistings werden nicht aus dem ursprünglichen Empfehlungsuniversum entfernt.

Die Belege sind nachvollziehbare manuelle Quellenaussagen, keine kryptografische
Garantie ihrer inhaltlichen Wahrheit. Ein heutiges Stammdatenblatt beweist keine
historische Zuordnung; ein gesetztes JSON-Flag allein ist keine Quellenprüfung.

## Versionierte lokale Marktdaten

Bestehende Eingabeformate und vollständige Pflichtmetadaten:
[Backtesting V1](hebeltrader-backtest-v1.md#kursdaten-und-mapping).
Eine Quelle muss Nutzungsrechte, raw-OHLCV, Retrieval-Zeit, Abdeckung, Kalender,
Actions, Börse, Zeitzone und historisches Instrument belegen. CSV ist ein
Transportformat und keine Lizenz. V1.3 friert diese Daten ohne Netzwerk ein:

```bash
python -m scanner.hebeltrader market-snapshot \
  --input-dir /lokaler/market-root --spec source-spec.json \
  --snapshot-dir snapshots --output frozen-spec.json
```

Spec-, Ausgabe- und Snapshotpfade liegen unter `--input-dir`; der Quellbestand
bleibt unverändert, neue Snapshotdateien werden nur im expliziten Ziel angelegt.
Die Spec ist ein einzelnes Listingobjekt, nicht das äußere WKN-Mapping.
`frozen-spec.json` danach unter dem passenden WKN-/ISIN-Schlüssel ins Mapping
übernehmen. Manuelle Identitätsnachweise werden mit eingefroren; eine spätere
Änderung erfordert einen neuen Snapshot und gegebenenfalls neue Prüfung.

Snapshots erhalten eine SHA-adressierte Version und Manifest, Rohdatei-Hashes
sowie sämtliche unterstützte Quellen-/Lizenz-/Reviewmetadaten. Identische
Eingaben ergeben dieselbe Version; vorhandene Inhalte werden geprüft statt
überschrieben. Andere Retrieval-/Metadaten oder Bytes ergeben andere Versionen.
Publikation erfolgt über temporäres Verzeichnis und Rename, konkurrierende
lokale Publikationen werden serialisiert. Das ist **kein automatischer Download**.
Credential-Felder und URLs mit Userinfo/Query/Fragment werden nicht archiviert;
Zugangsdaten gehören außerhalb von Specs, Repository und Logs.

`SnapshotStockProvider` prüft Manifest und eingefrorene Bytes und vergleicht
anschließend auch die Hashes der tatsächlich vom CSV-Leser verwendeten Bytes.
Veränderte, malformed oder unvollständige Snapshots liefern keine Bars und
`snapshot_hash_mismatch`. Die Versionskennung gelangt über die Identitätsauflösung
in die Coverage-Zeile. Normale lokale CSV-Specs bleiben für Inventur kompatibel,
aber nur ein eingefrorener Stand bietet unveränderliche Versionsreferenzen.

## Regel-Evidenz-Workflow

Pro Empfehlung werden vorhandene `rules.json`-Nachweise unabhängig geprüft.
Zusätzlich zeigt der Bericht Literalzitate mit PDF-Seite, Nähe zur
Empfehlungsseite, Trunkierungsflag und `requires_manual_review=true`.
Die begrenzte Stichwortsuche erkennt Regelkontext, **keine semantische Geltung**:
Zitate können zu einer anderen Empfehlung auf derselben Seite gehören.
Ohne passende Phrase wird nur der Seitenhinweis mit Prüfgrund gezeigt.

Prüfer lesen die Originalseite, bestätigen Instrument und geltende Regel ohne
Kenntnis des späteren Kursverlaufs und übertragen erst dann die passenden
Originalzitate nach SHA/Ordinal in rules.json. Die bisherigen V1.2-Prüfungen
verifizieren Datum, Seite und Zitat. Es gibt keinen Auto-Approve-/Trainings-
Schalter und keine pauschale Übernahme der 20-Tage-/Stopp-2-Regel.

## Tatsächlicher Ausgangsbericht der 118 Originale

Am 22.10.2026 wurden die bereits lokal vorliegenden autorisiert bezogenen
Original-PDFs ausschließlich in einer wegwerfbaren lokalen SQLite-Datenbank
importiert und zweimal mit festem Stichtag/Replayschlüssel inventarisiert.
Kein Hetzner-Zugriff. [Aggregierter Originalbericht](hebeltrader-coverage-v13-baseline.json)
enthält keine Originalzitate. Private vollständige JSON-/CSV-Berichte liegen
außerhalb des Repositories unter `/workspace/artifacts/hebel-coverage-v13/`.

- 118 Empfehlungen, 118 belegte Publikationen, keine Zählabweichung.
- 114 Aktien-WKN, keine Aktien-ISIN, 116 belegte Aktienwährungen;
  vier fehlende Aktienidentifikatoren und zwei fehlende Währungen bleiben sichtbar.
- Je 0 bestätigte historische Listings, geprüfte rules.json-Zuordnungen,
  ausreichende Marktserien, ausführbare Entries und Derivat-Bid/Ask-Belege.
- 0 belegte Availability für den strengen Modus.

0 Markt-Coverage bedeutet hier konkret: **keine Mapping-/Regel-/Marktdateien
vorgelegt**, nicht 118 erfolglose Empfehlungen und nicht eine bewiesene
Unmöglichkeit aller Datenquellen. Originalzitate, Original-PDFs, echte Rohkurse
und Zugangsdaten wurden nicht in Git aufgenommen.

## Quellenentscheidung, Reproduktion und Rollout

[Quellen-/Kostenentscheidung](hebeltrader-backtest-sources.md) bewertet offizielle
Dokumentation von Yahoo/yfinance, Alpha Vantage und EODHD (EU/US, 2025–2026,
Delistings, Kalender, Actions, Lizenz-/Free-Limit-Grenzen). Tatsächliche
118-Instrument-Coverage und geeignete Rechte für einen bezahlten Anbieter sind
weiterhin nicht belegt. Deshalb: EUR 0 Integrationskosten für den Offline-Weg,
kein Abo oder bezahlter API-Aufruf. Ein Providervertrag darf erst nach konkreter
Coverage-/Rechteprüfung und separater Kostenfreigabe eingeführt werden.

Kleines vollständig [synthetisches Beispiel](examples/coverage-v13/coverage.json)
mit CSV und Zusammenfassung im selben Ordner. Eine vollständige künstliche
118-Zeilen-Inventur lässt sich ohne konfigurierte DB oder Netzwerk reproduzieren:

```bash
PYTHONPATH=.:tests/hebeltrader python tests/hebeltrader/generate_coverage_example.py \
  --output-dir /tmp/neues-coverage-beispiel
python -m pytest -q
# Ausschließlich eine wegwerfbare PostgreSQL-Testdatenbank:
TEST_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/TESTDB' python -m pytest -q
ruff check .
ruff format --check .
```

Generator nutzt ausschließlich eine In-memory-SQLite-DB und ignoriert
DATABASE_URL. Datum, Quelldateien, Identitäten und Preise sind dort erfunden.
Der Produktivbefehl akzeptiert dagegen die bestehende PostgreSQL-Datenbank nur
lesend. Neue Ausgabenamen erlauben beliebig wiederholte Inventuren ohne Duplikate
oder Datenänderung; für bytegleiche Berichte DB-/Inputstand und --run-at fixieren.

Kein Deployment und keine Migration erforderlich. Ein späterer separater
Betreiberlauf kann nach Imagebau im getrennten Scanner-Projekt
`docker compose --profile analysis run --rm --no-deps pdf-import python -m
scanner.hebeltrader coverage ...` verwenden. Pfade explizit read-only einbinden,
Berichtspfad für UID 10001 gemäß bestehender Anleitung bereitstellen.
Keine anderen Docker-Projekte oder Immich-Dienste müssen geändert werden.

## Ausgeführte Verifikation

Am 22.10.2026: vollständige Suite mit **246 erfolgreichen Tests**, einschließlich
wegwerfbarem PostgreSQL 17.6 und 118-Zeilen-READ-ONLY-Test. Danach ergänzter
Snapshot→Identity→Coverage-Integrationstest zusammen mit den neuen Modulen
erneut erfolgreich geprüft. Ruff, Formatierung und git diff --check bestanden;
unabhängiges Review ohne verbleibende blockierende Befunde. Die vollständige
Suite sowie Compose-/Docker-/Migrationsprüfungen laufen zusätzlich in GitHub-CI.
Original- und synthetische 118-Zeilen-Inventuren wurden lokal erstellt; keine
Hetzner-Kommandos oder Änderungen produktiver Daten.
