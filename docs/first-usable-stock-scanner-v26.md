# Scanner V6 V2.6 – kontrollierte Marktabdeckung

Stand: 25. Oktober 2026. V2.6 erweitert den real geprüften Neun-Titel-Datenbestand in
reproduzierbaren Seiten. Das Ziel sind zunächst mindestens 100 US-Aktien mit jeweils mindestens
250 Sitzungen. Ein Bericht gilt erst als `accepted`, wenn auch der unabhängige Börsenkalender alle
Sitzungen bestätigt. Fixtures und modellierte Verfügbarkeit können diese Abnahme nicht erfüllen.

## Daten- und Rechtegrenzen

Tiingo bleibt für diesen internen Pilot der gewählte EOD-Anbieter. Maßgeblich sind die
[Preisübersicht](https://www.tiingo.com/pricing) und die
[EOD-Dokumentation](https://www.tiingo.com/documentation/end-of-day). Der zuletzt dokumentierte
kostenlose Starter-Rahmen beträgt 500 eindeutige Symbole pro Monat, 50 Requests pro Stunde,
1.000 Requests pro Tag und 1 GB pro Monat; die Daten sind für interne Nutzung vorgesehen. Diese
Angaben müssen vor jedem späteren Tarif- oder Produktwechsel erneut geprüft werden. V2.6 bucht
nichts und setzt die Projektkosten auf 0 EUR.

Der lokale, SHA-verkettete Quotenledger reserviert Kapazität **vor** dem Netzwerkzugriff. Eine
Reservierung wird nach einem Fehler nicht zurückgegeben. Das ist absichtlich konservativ und
verhindert, dass Neustarts die Grenze umgehen. Der API-Schlüssel wird nur als Laufzeitvariable in
den Container gereicht und erscheint weder im Image noch in Archiven oder Berichten.

Tiingo-EOD sind Composite-Tagesdaten, keine ausführbaren Quotes. Bid, Ask und Spread bleiben
unbekannt. `retrieved_at` und die erste lokale Speicherung belegen nur den tatsächlichen Abruf;
eine modellierte Verfügbarkeit zum damaligen Börsenschluss bleibt hypothetisch und
`training_eligible=false`.

## Identität, Kalender und Benchmark

Die Seitenauswahl basiert ausschließlich auf einem SHA-geprüften SEC-Universum. CIK, Ticker,
Börsenplatz und MIC müssen widerspruchsfrei sein; Mehrfachlistings werden weiterhin ausgeschlossen.
Die Auswahlreihenfolge ist ein stabiler SHA-256-Rang der CIK und hängt weder von späterer Rendite
noch von Teaserwissen ab.

Ein offizieller Kalender wird als archivierte CSV mit `session_date,close_at`, Quellen-URL,
Abrufzeit und SHA-256 eingebunden. Ohne solchen Beleg lautet der Status
`unavailable_not_inferred`; Wochenenden oder vorhandene Kurszeilen werden nicht zu einem Kalender
umgedeutet. Feiertage und verkürzte Sitzungen müssen für XNYS, XNAS und XASE belegt sein. Die
offiziellen jährlichen Veröffentlichungen von
[NYSE](https://www.nyse.com/markets/hours-calendars) und
[Nasdaq](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule) sind geeignete
Ausgangsquellen, aber noch kein automatisch lizenzierter Massendatensatz.

SPY wird unter `benchmark:SPY` und MIC `ARCX` getrennt gesammelt. Er ist ausschließlich Benchmark,
niemals SEC-Unternehmenskandidat. Relative Stärke wird nur berechnet, wenn das Benchmarkarchiv den
gleichen Stichtag abdeckt.

## Inkrementelle Aktualisierung und Korrekturen

Ein Erstabruf lädt den konfigurierten Zeitraum. Weitere Läufe beginnen zehn Kalendertage vor der
zuletzt archivierten Sitzung. Unveränderte Zeilen bleiben idempotent; geänderte Providerwerte
werden als neue Revision bewahrt. Der Bericht trennt neu abgerufene Zeilen von den gesamten
archivierten Sitzungen sowie Zahl und Umfang der Revisionen. Splits und Dividenden stammen nur aus
den Providerdaten und werden nie ergänzt oder geschätzt.

Providerfehler werden pro Instrument festgehalten. Ein Fehler beendet nicht die gesamte Seite;
Retries bleiben im Client auf drei Versuche und im Quotenledger auf die reservierte Obergrenze
beschränkt. Ein späterer Lauf kann denselben Offset wiederholen und verwendet bereits archivierte
Rohantworten ohne neuen Request.

## Isolierter Hetzner-Lauf

Der Lauf verwendet kein Compose, kein PostgreSQL und kein Immich-Netzwerk. Er schreibt nur nach
`/opt/scanner-v26-market-data`. Pro UTC-Stunde wird wegen der kostenlosen Grenze höchstens eine
40er-Seite mit maximal 50 Requestversuchen ausgeführt:

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/first-usable-stock-scanner-v26
git worktree add --detach /opt/scanner-v26 \
  origin/feat/first-usable-stock-scanner-v26
cd /opt/scanner-v26

BATCH_OFFSET=0  BATCH_COUNT=40 bash scripts/run-tiingo-expansion.sh
# In einer späteren UTC-Stunde:
BATCH_OFFSET=40 BATCH_COUNT=40 bash scripts/run-tiingo-expansion.sh
# In einer weiteren UTC-Stunde:
BATCH_OFFSET=80 BATCH_COUNT=20 bash scripts/run-tiingo-expansion.sh
```

SPY wird in einer weiteren UTC-Stunde mit einem eigenen, auf drei Versuche begrenzten Lauf
archiviert:

```bash
bash scripts/run-tiingo-benchmark.sh
```

Jeder Aufruf fragt den erneuerten Schlüssel verdeckt ab. Er darf nicht in den Chat oder die
Shell-History kopiert werden. Der Gesamtbericht entsteht danach komplett offline:

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount type=bind,src=/opt/scanner-v26-market-data,dst=/output \
  scanner-v26-market-data python -m scanner.market_data.cli aggregate \
  --market-db /output/market-data.sqlite \
  --output /output/coverage-100 --target-count 100 \
  /output/batch-0000.json /output/batch-0040.json /output/batch-0080.json
(cd /opt/scanner-v26-market-data && sha256sum -c coverage-100.sha256)
```

`partial` ist ein valides Ergebnis und benennt fehlende Titel, weniger als 250 Sitzungen,
Providerfehler oder unbelegte Kalendersitzungen. Nur der reale Serverlauf darf die tatsächliche
Abdeckung feststellen.

## Nachrichten und die zwei Recherchekanäle

Der bestehende, explizit freizugebende Issuer-Feed-Adapter akzeptiert nur einzeln erlaubte
offizielle RSS-/Atom-Feeds mit dokumentierter Lizenz und unveränderlichem Cache. SEC-Dokumente und
Issuer-Meldungen sind Primärquellen; GDELT ist Discovery, keine unabhängige Bestätigung. Paywalls,
Captchas oder Zugriffsschutz werden nicht umgangen.

Der Opportunity-Scanner hält zwei Auslöser fachlich getrennt:

1. belegter Unternehmenskatalysator mit anschließender Marktbestätigung;
2. technischer Momentumimpuls durch Ausbruch oder ungewöhnliches Volumen.

Community-Aufmerksamkeit bleibt Zusatzkontext. Fehlender Kalender, ungeprüfter Instrumenttyp,
fehlender Benchmark oder fehlende Ausführungsquotes verhindern weiterhin ein belastbares
Handelssignal. V2.6 kann deshalb trotz breiterer realer Daten korrekt null Kandidaten melden.

Ein späterer Forward-Monitor protokolliert pro Lauf Datenstand, Cutoff, Universumsabdeckung,
Kandidaten, Watchlist, Ausschlüsse, nächste zulässige Sitzung und spätere Outcomes. Er erzeugt
keine Order und darf erst nach einem eingefrorenen Walk-forward-Protokoll Trainingslabels setzen.

## Reale Hetzner-Abnahme: 100 Aktien

Der isolierte Lauf vom 25. Oktober 2026 hat alle drei vorab bestimmten SEC-Seiten erfolgreich
abgerufen und ihre Einzelberichte per SHA-256 geprüft:

- Offset 0: 40 von 40 importiert, Bericht-SHA
  `fd91a8d8236ac9bd7bedbc354998c38ea8c716a3ed3883985236d868201e6479`;
- Offset 40: 40 von 40 importiert, Bericht-SHA
  `30adae620a128395a96b8828f0c298aec2018a68c6c65dd17259669e5c5c8695`;
- Offset 80: 20 von 20 importiert, Bericht-SHA
  `047f48243812612373d8a79a50d2ff6cdb0e0637d97ecfe69f8ecc1dc2992f22`.

Der aggregierte Bericht enthält 100 eindeutige Instrumente, 100 erfolgreiche Importe, keine
Identitätskonflikte und 92 Reihen mit mindestens 250 Sitzungen. Acht Reihen bleiben ohne
Ursachenbehauptung unvollständig: RYZ 169, SGP 180, VOGX 52, BSP 81, SOEZ 224, BRAI 176, EROC 95
und CTY 6 Sitzungen. Listingbeginn, Delisting, Symbolwechsel und Providerabdeckung müssen dafür
getrennt anhand zeitlich passender Primärquellen geprüft werden.

Der Gesamtstatus lautet weiterhin `partial`: Für keine der 100 Reihen wurde bereits ein
SHA-archivierter offizieller Handelskalender eingebunden. Der Lauf belegt reale Providerabdeckung,
aber noch keinen kalenderverifizierten Backtestbestand.

Der getrennte SPY-Lauf wurde anschließend mit einem Providerrequest erfolgreich abgeschlossen:

- Identität und Rolle: `benchmark:SPY`, `benchmark_only_not_candidate`;
- 454 archivierte Sitzungen, Mindestumfang von 250 Sitzungen erfüllt;
- Bericht-SHA: `bcac45a1adf1367e89cf1b7d3704ddb3dd577e483cfb62060249d2589c815377`;
- Rohdaten-SHA: `b44de1ee6e2f11745952e8fe36ef45480e7b97ec2bc5c17fca84ecd22ca388f1`;
- Manifest-SHA: `1238de2f4cd2e94d2ac1906a9a740f13384ec7bffbd91b46450162675fa94c4a`;
- logischer Archiv-SHA nach SPY:
  `9da9dacb0f5deeb5e3725319ff86dea60c5d317ae2619e041d19255b2d0a0105`.

Auch SPY trägt `calendar_status=unavailable_not_inferred`. Er ermöglicht damit eine reale,
modellierte Relative-Stärke-Berechnung auf demselben Providerarchiv, belegt aber noch keine
historische Datenverfügbarkeit oder kalenderverifizierte Ausführung.

Nach dem SPY-Import muss `coverage-100` offline erneut aggregiert werden, damit sein
`archive_sha256` den nun erweiterten Archivstand bindet. Anschließend läuft der Scanner mit
`benchmark:SPY` vollständig offline und read-only:

```bash
SIGNAL_DATE=2026-10-23 bash scripts/run-expanded-opportunity-dry-run.sh
```

Das Signaldatum muss eine tatsächlich gewünschte abgeschlossene Sitzung sein. Ohne offiziellen
Kalender bleibt auch dieser Lauf `modeled_research`; die Ausgabe darf keine historisch verifizierte
oder ausführbare Empfehlung behaupten.
