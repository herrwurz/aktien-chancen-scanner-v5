# Scanner V6 V2.4 – Research-Index und News-Collector

## Ergebnis

V2.4 baut auf PR #19 auf und ergänzt eine gemeinsame, schreibgeschützte Recherchebasis. Ein
versioniertes SQLite-FTS5-Artefakt indexiert das vollständige jeweils archivierte SEC-Universum,
zeitgültige Unternehmensereignisse, Fakten und normalisierte Nachrichtenmetadaten. Der
HEBELTRADER-Detektiv nutzt den Index für eine breite Stage-A-Vorauswahl bis 50 Kandidaten; sein
bestehendes Stage-B-Ranking erzeugt danach höchstens drei Ergebnisse. Die Schnittstelle für den
Aktien-Chancen-Scanner liefert nur Datenverfügbarkeit, noch keine Kaufentscheidung.

Implementierte neue Quellen:

- **GDELT DOC 2.0:** begrenzter, explizit aktivierter Metadatenadapter. Er speichert URL, Titel,
  Zeitpunkt und Provenienz, aber keinen fremden Artikeltext. Zwei reale Abnahmeabrufe endeten am
  24.10.2026 jeweils mit HTTP 503. Der Ausfall ist im Bericht sichtbar; es gibt keinen Demo-Fallback.
- **Allowlisted RSS/Atom:** nur explizit konfigurierte Emittentenfeeds mit belegter Kennung und
  dokumentiertem Lizenzverweis. XML-Größe, Entitäten/DOCTYPE, Netzwerk, Requests und Timeout sind
  begrenzt. Rohfeeds werden unveränderlich mit SHA-256 archiviert. Die konkrete produktive
  Metadatennutzung muss je Feed weiterhin rechtlich freigegeben werden.

SEC EDGAR und GLEIF bleiben unverändert erhalten. Die vollständige Quellenentscheidung steht in
[research-v24-source-audit.md](research-v24-source-audit.md).

## Reale End-to-End-Abnahme

Der reale Lauf verwendete:

- das am 24.10.2026 archivierte SEC-Universum mit 10.425 Listings und 8.022 eindeutigen CIKs;
- den offiziellen Apple-Newsroom-RSS-Feed mit 20 Metadatensätzen;
- zwei Blindhinweise ohne Firma, Ticker, WKN, ISIN oder CIK;
- Point-in-time-Grenze `2026-10-24T06:30:00Z`;
- null kostenpflichtige Requests.

Die Regression `new product` endet nun `unresolved`, weil kein einzelner Evidenzsatz beide Wörter
belegt. Die früheren BlackRock-Fonds MUJ und MYN werden nicht mehr aus dem bloßen Namenswort
„New“ erzeugt. Der spezifischere Hinweis `smart home accessories` liefert aus der realen
Emittentenmeldung genau AAPL. Das ist ein realer Datenfluss und eine nachvollziehbare
Kandidatengenerierung, aber kein unabhängiger Recall-Nachweis: Der einzige aktive Newsfeed gehörte
Apple und beide Abfragen wurden nach Auswahl des Feeds festgelegt. Der maschinenlesbare Bericht steht in
[research-v24-e2e.json](research-v24-e2e.json).

## Kandidatenqualität und Benchmark

Identitätsnamen und Evidenztitel besitzen getrennte FTS-Kanäle. Alle Suchbegriffe müssen innerhalb
eines Datensatzes vorkommen; ein Identitätstreffer allein ist schwach und darf keine Identifikation
auslösen. Belegte Branchen und Ereignisse wiegen stärker. SEC-Rechtsträger mit eindeutigen
Fondsmerkmalen im Namen erhalten `instrument_type=fund`, Status `inferred` und den Beleg
`sec_legal_name_pattern`; unbekannte Typen bleiben `unknown`.

Der vorab gespeicherte Funktionskorpus enthält zehn kennungsfreie Fälle aus zehn Sektoren und den
Märkten US, DE, AT, CH und CA: acht lösbare Fälle, einen absichtlich mehrdeutigen Fall und einen
Fall außerhalb der Abdeckung. Alle Fälle sind **synthetisch**. Ergebnis: Recall@10/50 und
Top-1/Top-3 jeweils 1,0, Abstention 1,0 und False-Positive-Rate@3 0,0. Diese Werte prüfen die
Rankingregeln; sie belegen keine reale Marktgüte. Definition und Ergebnis stehen in
`tests/fixtures/research-v24/candidate-benchmark.json` und `research-v24-benchmark.json`.

## Evidenz und Deduplizierung

Meldungen werden als `PRIMARY`, `SECONDARY` oder `COMMUNITY` gespeichert. Community-Inhalte können
keinen verifizierten Unternehmensfakt erzeugen. Cluster verwenden belegte Kennungen, Ereignisart,
36-Stunden-Fenster, Titelähnlichkeit und `origin_id`. Syndikationskopien behalten ihre URLs, zählen
aber nur einmal je Ursprung. Ähnliche Firmennamen erzeugen ohne eindeutigen Alias-/Kennungstreffer
keine Zuordnung.

`published_at`, `first_seen_at`, `retrieved_at`, `actual_event_at` und
`source_available_at` bleiben getrennt. Historische Abfragen sehen Identitäten, Fakten und
Meldungen erst ab ihrer belegten Verfügbarkeit. Spätere XBRL-Korrekturen bleiben durch die
V2.3-Regeln ausgeschlossen, bis ihre eigene Verfügbarkeit erreicht ist. Explizit verknüpfte
Nachrichten- und Kennzahlrevisionen ersetzen einen früheren Stand erst ab dem eigenen
`source_available_at`; historische Abfragen davor behalten den Originalstand.

Jeder Nachrichtenbatch kann sein Alter gegen eine explizite `as_of`-Grenze und ein maximales
Alter als `fresh`, `stale` oder `unavailable` ausweisen. Ein nicht erreichbarer IR-Feed liefert
einen strukturierten `unavailable`-Status samt verbrauchtem Request statt scheinbarer Leerdaten.
Die Evaluationsausgabe aggregiert nur tatsächlich gemessene Laufzeiten, Requests und Kosten;
fehlende Messwerte werden nicht als null ausgegeben.

## Gemeinsame Schnittstellen

`IndexedResearchService` stellt `universe`, `candidates`, `events`, `fundamentals`, `prices` und
`coverage` bereit. Für `short_term_trading` und `medium_term_investing` werden erforderliche und
fehlende Felder ausgewiesen. Ohne Kurs, Volumen, Liquidität, Bewertung oder Trend bleibt der
Entscheidungsstatus `unavailable`.

## Reproduzierbarer Offline-Lauf

```bash
python -m scanner.research_v24_report \
  --sec-universe-request reports/research-v24/sec-cache/requests/UNIVERSE.json \
  --news-batch reports/research-v24/issuer-feed.batch.json \
  --index reports/research-v24/research-index.db \
  --query 'smart home accessories' \
  --as-of 2026-10-24T06:30:00Z \
  --output reports/research-v24/report.json
```

Der Befehl führt keine Migration und keinen Netzwerkabruf aus. Er prüft den SEC-Rohdatenhash, baut
den Index atomar neu und erzeugt bei identischen Eingaben denselben Payload-Hash.

```bash
python -m scanner.research_benchmark \
  --definition tests/fixtures/research-v24/candidate-benchmark.json \
  --index reports/research-v24/benchmark.db \
  --output reports/research-v24/benchmark.json
```

Der `ranking_payload_sha256` ist ohne die laufzeitabhängige Latenzmessung reproduzierbar.

## Verbleibende Lücken

- EQS/GlobeNewswire benötigen einen belastbaren API-/Lizenzentscheid vor Integration.
- GDELT war während der realen Abnahme nicht verfügbar und liefert ohnehin nur Discovery-Metadaten.
- Ein Feed pro Emittent skaliert erst mit einem geprüften Feedkatalog und Update-Scheduler.
- Es fehlt ein vorab registrierter, ausreichend großer **realer** Teaserkorpus für belastbare
  Recall@10/50- und Top-1/Top-3-Aussagen.
- Kurs-, Volumen-, Liquiditäts-, Spread-, Bewertungs- und Analystendaten fehlen für Chancen-Signale.
- Für den realen RSS-Test ist vor produktiver Aktivierung eine abschließende rechtliche Prüfung der
  Metadatenspeicherung erforderlich.

Die Anwendung führt keine Trades aus und bezeichnet Scores weder als Wahrscheinlichkeit noch als
Kaufsignal.
