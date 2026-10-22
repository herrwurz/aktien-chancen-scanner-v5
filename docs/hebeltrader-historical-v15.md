# Scanner V6 – historische Identitäten und Marktdaten V1.5

V1.5 ergänzt den aktuellen main einschließlich PR #10. Importparser, Original-PDFs,
Datenbankmodelle und bestehende Daten bleiben unverändert. Neue Funktionen sind
explizite CLI-Kommandos; es gibt keinen Scheduler, Trade oder Live-Signal-Aufruf.
Alle Beispiele sind Review-/Analysebefehle, keine Installation auf Hetzner.

## Tatsächlicher Bestand und Grenzen des Laufs

[Reproduzierbarer Bestandsbericht](hebeltrader-historical-v15-baseline.json):
118 Empfehlungen, 114 vorhandene WKN-Vorkommen, 96 unterschiedliche WKN, vier
Empfehlungen ohne Aktienkennung und eine Klassifikationskollision. Es wurden
keine vorhandenen Werte korrigiert oder V1.4-Vorschläge automatisch freigegeben.

Der Nutzer hat folgende Ergebnisse des Hetzner-Laufs mitgeteilt: 94 der 96 WKN
besitzen aktuelle OpenFIGI-Kandidaten; ohne Treffer sind 578560 und SJ6B4A.
Diese Dateien liegen ausschließlich dort:

- `/opt/aktien-chancen-scanner-v5/reports/hebeltrader/preparation-v14/openfigi.json`
- gleiches Verzeichnis: `openfigi-raw/`, `preparation-openfigi.identities.json`
  und `preparation-openfigi.json`.

Diese Dateien wurden in dieser Entwicklungsumgebung **nicht gelesen**. Der
lokale Lauf weist daher `openfigi_input_status=not_supplied` aus und trennt die
94 extern gemeldeten Treffer von null lokal geprüften Trefferdateien. Null
beobachtete Börsenplatzkonflikte bedeuten bei fehlender Eingabe nicht, dass die
94 Treffer eindeutig wären. Die Einlesefunktion unterstützt den V1.4-Originalexport
`{"records": [...]}` und prüft die angegebenen Rohantworten einschließlich ihrer
SHA-256- und JSON-Pointer-Bindung. Mehrere FIGI-/Börsenplatzkandidaten werden
vollständig erhalten; `exchCode=US` oder `GR` wird nicht in eine MIC umgedeutet.

**Echte historische Kursreihen importiert: 0. Historisch verifizierte Identitäten:
0. Für Forschungs- oder verifizierten Backtest freigegeben: jeweils 0/118.**
Es wurde kein EODHD-Netzwerkabruf ausgeführt. Zugangsdaten, ein freigegebener
Anbieterzugang und die Hetzner-Exportdateien sind hier nicht vorhanden. Die
funktionierende Verbindung bis zum Forschungsbereitschaftsbericht ist mit
synthetischen Offline-Daten getestet; das zählt nicht als echte Datenabdeckung.

## Gezielte Identitätsbefunde

### Fresenius, alte WKN 578560

Zwei Originalempfehlungen nennen 578560: 31.01.2025 (SHA f0f31767…) und 09.04.2025
(SHA b4a6bf0f…). Die Aktien-WKN ist jeweils auf PDF-Seite 3 belegt, während die
Optionsscheine auf Seite 1 andere WKN besitzen.

Die [Fresenius-FAQ](https://www.fresenius.com/faq) nennt die alte Inhaberaktie als
WKN 578560 / ISIN DE0005785604 und die neue Namensaktie als FRE5EN /
DE000FRE5EN2. Die [Mitteilung des Emittenten](https://www.fresenius.com/Fresenius-transitions-to-registered-shares)
belegt die technische Umstellung nach Handelsschluss am 12.08.2026 und den
Handel unter der neuen Kennung ab 13.08.2026, im Verhältnis 1:1; Ticker FRE
bleibt unverändert. Quellenstand der Recherche: 22.10.2026.

Daraus folgt keine automatische heutige Zuordnung der 2025er Empfehlung. Ein
aktueller Lookup kann die alte Kennung übersehen; der konkrete Grund des
OpenFIGI-Nichttreffers ist damit nicht nachgewiesen. Benötigt werden zusätzlich
datierte Listing-/MIC-/Währungsbelege und eine manuelle Bestätigung der jeweiligen
Gültigkeitsintervalle. Die Pipeline verbindet Kennungsintervalle nicht stillschweigend.
Ein Fenster über einen Kennungswechsel hinaus bleibt gesperrt, bis die
Kontinuität gesondert belegt und unterstützt ist. Die alte Kennung wird nicht als
Delisting mit fiktivem Verkauf behandelt.

### SJ6B4A / Daimler Truck

Im Original vom 19.01.2026 (SHA dbc17ac8…) steht SJ6B4A sowohl beim Optionsschein
auf Seite 1 als auch als WKN im Aktienabschnitt auf Seite 3. Die minimalen
Seiten-/Bounding-Box-Belege sind eine Offline-Regression. Das ist eine
**Kollision im Original**, kein durch uns korrigierter Parserwert. Die WKN wird
für historische Aktienzuordnungen quarantänisiert, auch wenn eine Mappingdatei
sie einfach als `verified` bezeichnet.

Die [Daimler-Truck-IR-Seite](https://www.daimlertruck.com/en/investors/share) nennt
für die Aktie WKN DTR0CK, ISIN DE000DTR0CK8 und Ticker DTG; ihre Tabelle nennt
unter anderem einen Stand vom 04.11.2025. Das ist ein Recherchebeleg für eine
mögliche Korrektur, keine automatisch angewandte historische Zuordnung. Ob
SJ6B4A tatsächlich ein bestimmtes Derivat identifiziert, wird ohne weitere
Emittentenbelege nicht behauptet. Originaldaten bleiben unverändert; eine
separat geprüfte Korrektur der Empfehlungszuordnung ist weiterhin erforderlich.

## Manuelle historische Freigabe

Aktuelle OpenFIGI-Ergebnisse bleiben immer unverified. Ein bestätigter Datensatz
benötigt WKN, checksumgeprüfte ISIN, konkretes Anbieter-Tickersymbol, MIC,
Börsenzeitzone, Währung, `identity_valid_from`, `identity_valid_until`,
`asset_class=stock`, Reviewer und einen zonierten Prüfzeitstempel. Bei mehreren
passenden Listings entscheidet die Pipeline nicht automatisch. Ein vorhandenes
`identity_status=verified` allein reicht nicht.

Zusätzlich wird jedes dieser Felder über `review_evidence` an eine datierte,
manuell gesammelte `historical_source` gebunden. Das Format erweitert die
bestehenden V1.4-Quellendatensätze:

```json
{
  "query_wkn": "AB1234",
  "provider": "historical_source",
  "retrieved_at": "2026-10-22T00:00:00+00:00",
  "source_reference": "https://issuer.example/dated-source",
  "license": "Permitted private research; synthetic example",
  "payload": {"wkn": "AB1234", "asset_class": "stock"},
  "payload_sha256": "SHA256_OF_CANONICAL_PAYLOAD"
}
```

Das ist ein unvollständiges, ausdrücklich synthetisches Schemafragment. Die echte
Quelle muss auch die übrigen Felder belegen. Der Payload-Hash verwendet
`json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)`
mit Python-Standard-ASCII-Escaping und SHA-256 über die UTF-8-Bytes, ohne Newline.
Ein Feldbeleg im manuell bestätigten Mapping sieht beispielsweise so aus:

```json
{"review_evidence": {"wkn": {
  "payload_sha256": "SHA256_OF_CANONICAL_PAYLOAD", "pointer": "/wkn"
}}}
```

Für ISIN, symbol, venue, timezone, currency, beide Gültigkeitsgrenzen und
asset_class sind entsprechende Belege Pflicht; bei angegebenem `delisted_at`
auch für dieses Feld. Quellenabruf und Prüfung dürfen nicht in der Zukunft des
Auditlaufs liegen; ein Reviewer kann keine erst später abgerufene Quelle belegen.
Die Quellen müssen die fachliche Aussage tatsächlich tragen. Ein Hash beweist
Integrität, keine externe Authentizität. Manuell normalisierte Quellen dürfen
keine erfundenen Inhalte enthalten. Der Operator muss Quelle und Nutzungsrecht
prüfen. Heutige Ticker oder ISIN werden niemals automatisch rückdatiert.

## EODHD: Freigaben, Kosten und Datensemantik

Der Collector liest den Schlüssel ausschließlich aus `EODHD_API_TOKEN` in der
Prozessumgebung. Eine `.env`-Datei wird dafür nicht automatisch exportiert. Schlüssel
nicht in Befehlszeilen, URLs, Repository oder Berichte schreiben; vorhandene
sichere Secret-Verwaltung verwenden. HTTPX-/HTTPCore-Logs redigieren api_token.
Ausnahmen geben nur bereinigte Fehlerklassen aus, keine authentifizierten URLs.

Ohne vorhandenen Cache sind **alle drei** Freigaben erforderlich:
`--allow-network`, `--authorize-provider-usage` und ein positiver
`--max-requests`-Wert. Diese Parameter erst nach ausdrücklicher Freigabe des
konkreten Anbieterzugangs verwenden. Ein Token oder das Budgetlimit ist keine
Kauf-/Abfragefreigabe. Es werden keine Abos eingerichtet oder Zahlungen ausgelöst.
Cachetreffer funktionieren vollständig offline.

`--monthly-total-eur` deklariert die vom Operator geprüften gesamten monatlichen
Anbieterkosten; Werte außerhalb 0–100 EUR werden abgelehnt. Die Anwendung kennt
keine Rechnungen, Steuern oder Wechselkurse und ersetzt keine zentrale
Budgetkontrolle. HTTP-Versuche und konservativ verbrauchte API-Einheiten werden
begrenzt. Fundamentals benötigen laut Anbieter 10 Einheiten pro Versuch;
`--max-api-units` muss diese explizit erlauben. Standardmäßig entsprechen die
Einheiten dem Request-Limit. Jeder Retry verbraucht Budget. Maximal drei Versuche,
15 Sekunden Timeout je Versuch, mindestens eine Sekunde Abstand bei weiteren
Requests und höchstens vier Sekunden Retry-Pause. Riesige Retry-After-Werte werden
nicht ungeprüft übernommen. Fehler und 429-Antworten werden nicht als Kursdaten gecacht.

Die [EOD-Dokumentation](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)
unterscheidet rohe OHLC, split-/dividendenbereinigtes `adjusted_close` und bereits
splitbereinigtes Volumen. V1.5 verwendet für Kursmarken **nur rohe OHLC**.
`adjusted_close` ersetzt weder Close noch historische Einstiegspreise. Volumen
bleibt als `split_adjusted_vendor` gekennzeichnet und ist keine belegte historische
Volumen-Vintage für Trainingssignale. Abruf-Snapshots belegen den späteren
Datenstand, keine damalige Datenverfügbarkeit. `training_eligible=false` bleibt.

Splits und Dividenden werden als eigene Ereignisse mit effektiven Datumsangaben
aufbewahrt. Ohne abgestimmte Positions-/Kursmarken-/Cashflow-Behandlung blockieren
sie den Backtest. Ein Delisting erzeugt ebenfalls einen Blocker, keinen erfundenen
Verkauf zum letzten Close. Historische/inaktive Symbole können über
[Exchange Symbol List / delisted=1](https://eodhd.com/financial-apis/delisted-stock-companies-data-2)
recherchiert werden; aktive und inaktive Listen sind getrennte Abfragen. Sie
ersetzen keine manuell belegte Datierung der Listing-Gültigkeit.

EODHD `US` ist ein Anbietercode für einen US-Marktverbund, keine MIC. Eine manuell
belegte MIC beschreibt das Listing; ein EODHD-Tageswert ist kein Nachweis einer
ausführbaren Transaktion an genau diesem Platz. Es werden keine Bid-/Ask-,
Optionsschein- oder Ausführungsbehauptungen aus Aktien-OHLC abgeleitet.

### Anbieterwahl innerhalb des Budgets

Stand der öffentlichen Recherche 22.10.2026 nennt die
[Anbieterübersicht](https://eodhd.com/financial-academy/financial-faq/the-2026-market-data-api-scorecard-comparing-6-leading-providers)
EOD All World mit 19,99 USD/Monat, EOD+Intraday mit 29,99 USD, Fundamentals mit
59,99 USD und All-in-One mit 99,99 USD. Das sind Referenzpreise, keine gebuchten
Leistungen oder garantierten EUR-Endpreise. Für V1.5 wäre nach Freigabe zunächst
nur EOD zu prüfen; das teurere All-in-One ist keine Voraussetzung.
[Quick Start](https://eodhd.com/financial-apis/quick-start-with-our-financial-data-apis)
nennt 20 API-Einheiten/Tag und nur ein Jahr Historie im kostenlosen Plan. Das
reicht für 96 vollständige Instrumenthistorien ab Anfang 2025 im Oktober 2026
nicht ohne weitere Prüfung. Schon EOD, Splits und Dividenden bedeuten mindestens
288 Requests für 96 Symbole, ohne Retries und Metadatenrecherche.

Alternativen sind etwa Twelve Data für internationale Aktien oder Massive für
US-Aktien. Venue-/Historienumfang, inaktive Listings, Corporate Actions und
Lizenzrechte müssten gesondert verglichen werden; ein US-Fokus deckt die gemischte
WKN-Liste nicht automatisch ab. Keine dieser Aktien-APIs liefert dadurch historische
Bid-/Ask-Daten deutscher Optionsscheine. Es wurde kein Anbieter aktiviert.

## Rohdaten, Kalender und unveränderliche Snapshots

EODHD-Antworten werden privat in `raw/<sha256>.json`, Metadaten in
`manifests/<sha256>.json` und eine unveränderliche Request-Referenz in `requests/`
gespeichert. Requestparameter enthalten Symbol und Datumsfenster, niemals den
Token. Dateien erhalten 0600, neue Cacheordner 0700. Jede Wiederverwendung prüft
Manifest- und Rohdaten-Hashes; Symlinks dürfen den Cache nicht verlassen. Ein
frischer Datenstand benötigt einen neuen Cacheordner, keinen überschreibenden
Refresh. Bei Fehlern kann ein Teilcache mit bereits gültigen Antworten verbleiben.

Die Normalisierung benötigt eine **unabhängig belegte historische Sitzungs-CSV**:
`timestamp,end_timestamp`, jeweils mit dem damals korrekten UTC-Offset des
Handelsplatzes. Feiertage, Sommerzeit und verkürzte Sitzungen werden dadurch
explizit berücksichtigt. Kalender werden weder aus vorhandenen Preistagen noch
aus heutigen Standardöffnungszeiten geschätzt. Eine alleinige aktuelle
[Trading-Hours-Antwort](https://eodhd.com/financial-apis/exchanges-api-trading-hours-and-stock-market-holidays)
ist noch kein vollständiger historischer Sitzungsbeleg. EODHD kann zusätzliche
Kalenderinformationen liefern; deren historische Gültigkeit muss separat geprüft
werden. V1.5 erfindet daraus keine Sitzungen.

EOD, Splits und Dividenden müssen dasselbe Symbol und ein ausreichend breites,
explizites Datumsfenster abdecken. Anfragegrenzen sind konservativ in der
Börsenzeitzone zu setzen; gegebenenfalls einen zusätzlichen Randtag abrufen.
Doppelte Kursdaten, ungültige OHLC, fehlende Sitzungszuordnungen, falsche Zeitzonen
und Zukunftsdaten werden zurückgewiesen. Fehlende Kurszeilen innerhalb des
Kalenders werden nicht aufgefüllt und verhindern ausreichende Marktabdeckung.

Die normalisierten CSVs werden über den bestehenden V1.3-`snapshot_dataset`
unveränderlich eingefroren. Das ausgegebene Bundle bindet dessen Hashversion
an die ursprünglichen EODHD-Rohmanifeste. Der Offline-Provider prüft beides erneut.
Bereits freigegebene Identitäts-Metadaten müssen **vor** der Snapshot-Erzeugung
vorliegen; eine spätere Änderung erfordert einen neuen Snapshot. Ein verändertes
Mapping darf nicht stillschweigend die eingefrorenen Metadaten übersteuern.

## Befehle für eine bereitgestellte lokale Datenkopie

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
export DATABASE_URL='sqlite:///file:/absolute/inventory.db?mode=ro&uri=true'
python -m scanner.hebeltrader historical-data audit \
  --as-of 2026-10-21T23:59:00+00:00 --run-at 2026-10-22T00:00:00+00:00 \
  --openfigi /private/copied-input/openfigi.json \
  --openfigi-cache /private/copied-input/openfigi-raw \
  --expected-count 118 --output-prefix /private/new-review/coverage
```

Vier neue Dateien: JSON/CSV für alle Empfehlungen sowie `.identities.json` und
`.identities.csv` für die 96 WKN. CSV `record_json` entspricht dem jeweiligen
JSON-Datensatz. Bestehende Dateien werden nicht überschrieben. Einen Replay-Zeitpunkt
nach allen tatsächlichen Quellenabrufen wählen. Für PostgreSQL wird
`SET TRANSACTION READ ONLY` gesetzt, für SQLite `PRAGMA query_only=ON`; empfohlen
ist zusätzlich ein eigener SELECT-only-Benutzer. Keine Migration ist erforderlich.

Nur nach ausdrücklicher Anbieterfreigabe und sicher bereitgestelltem Schlüssel:

```sh
python -m scanner.hebeltrader historical-data collect \
  --symbol "${REVIEWED_SYMBOL:?Set a manually checked vendor symbol}" \
  --from 2024-12-30 --to 2026-03-02 \
  --cache-dir /private/new-review/eodhd-raw \
  --output /private/new-review/raw-manifests.json \
  --allow-network --authorize-provider-usage --max-requests 3 \
  --max-api-units 3 --monthly-total-eur "${APPROVED_MONTHLY_TOTAL_EUR:?Confirm total cost}"
python -m scanner.hebeltrader historical-data normalize \
  --cache-dir /private/new-review/eodhd-raw \
  --raw-manifests /private/new-review/raw-manifests.json \
  --spec /private/reviewed-listing-and-window.json \
  --calendar /private/reviewed-historical-sessions.csv \
  --data-root /private/new-review/market \
  --run-at "${AUDIT_RUN_AT:?Set timestamp after retrieval}" \
  --output /private/new-review/bundle.json
```

Das Spec enthält insbesondere WKN/ISIN, symbol, venue, timezone, currency,
coverage_start/end, identity_reference, identity_valid_from/until und
calendar_reference; bestätigte Datensätze zusätzlich die Reviewer-/Belegfelder.
Datumsfenster und Sitzungen müssen zur gewünschten Empfehlungsperiode passen.
Diese Beispielkommandos werden hier nicht ausgeführt.

Für einen späteren Audit mit Daten ergänzen: `--historical-sources` (historische
Quellen im records-Format), `--map` (vollständiges Snapshot-Spec plus asset_class
und review_evidence je WKN), `--rules` (manuell freigegebene rules.json),
`--bundles bundle.json ...`, `--data-root` und `--eodhd-cache`. Nicht automatisch
extrahierte V1.4-Regeln als freigegeben behandeln. Beide Modi werden unabhängig
berechnet; `--analysis-mode` wählt die primäre Detailansicht, `mode_audit` enthält
zusätzlich die getrennten Forschungs-/Verfügbarkeitsprüfungen. Die bestehende
V1.3-Identitäts-/Kalender-/Quellenprüfung bleibt Bestandteil der Pipeline.

## Zum ersten belastbaren Backtest fehlen konkret

1. OpenFIGI-Originalexport und Rohantworten zur Offline-Prüfung bereitstellen.
   Mehrere Börsenplätze und historische Quellen je WKN manuell zuordnen.
2. Für zunächst eine konfliktfreie Empfehlung das historische Listing samt ISIN,
   MIC, Währung, Zeitzone und Gültigkeitsfenster mit datierten Quellen bestätigen.
   SJ6B4A bleibt bis zur gesonderten Korrektur der Zuordnung blockiert.
3. Anbieterplan, Nutzungsrechte und EUR-Gesamtkosten ausdrücklich freigeben;
   Schlüssel sicher bereitstellen. Dann OHLC, Splits und Dividenden abrufen und
   einen unabhängig belegten Kalender einfrieren.
4. Vollständige Handelsregeln manuell prüfen. Die V1.4-Typen target2_sale und
   conditional_loss_exit werden von der bisherigen Backtest-Engine noch nicht
   eigenständig validiert/simuliert und bleiben gesperrt. Solche Regeln dürfen
   nicht einfach entfernt werden, um einen Datensatz passend zu machen.
5. Corporate Actions und gegebenenfalls Delisting/Kennungswechsel explizit
   modellieren. Daten- und Regelprüfungen müssen danach ohne Blocker bestehen.
6. Forschungsergebnisse weiterhin hypothetisch ausweisen. Der strenge Modus
   benötigt zusätzlich echte historische Verfügbarkeitsbelege. Für eine tatsächlich
   ausführbare Transaktionsaussage fehlen weiterhin Kosten und Ausführungsmodell.

Für einen Optionsschein-Backtest fehlen zusätzlich historische Produktbedingungen,
Emittenten-/Börsenkurse mit Bid und Ask, Liquidität, Spread, Laufzeit-/Knockout-/
Ausübungsereignisse und Ausführungskosten. Aktien-OHLC ersetzen das nicht.

## Validierung und Docker

```sh
ruff check .
ruff format --check .
python -m pytest -q
# Rein offline, ohne lokale PostgreSQL-Instanz:
python -m pytest tests/hebeltrader tests/test_identity_assistant.py -q
# Optionaler lokaler Image-Build, kein Compose-Up/Deployment:
docker build -t scanner-v15-review .
```

GitHub Actions führt den vollständigen Testlauf einschließlich einer ausdrücklich
kurzlebigen Test-PostgreSQL-Instanz, Compose-Konfigurationsprüfungen und Docker-Build
aus. Produktionsdatenbanken werden nicht migriert. Die PostgreSQL-Regression
kontrolliert, dass der neue Audit nur SELECT und SET TRANSACTION READ ONLY ausführt.
Offline-Tests prüfen unter anderem Ablehnung unbelegter Freigaben, mehrere
FIGI-Börsenplätze, datierte Identitätsfenster, Original-SJ6B4A-Kollision, Rate-Limits,
Geheimnisschutz, Cache-/Snapshot-Integrität, Rohpreise gegenüber adjusted_close,
Sommerzeit-Offsets, verkürzte Sitzungen, fehlende Preistage, Splits, Delisting,
beide Backtest-Modi und einen vollständig synthetischen positiven Forschungsfall.
