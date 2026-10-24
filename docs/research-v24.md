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
- einen Blindhinweis `new product` ohne Firma, Ticker, WKN, ISIN oder CIK;
- Point-in-time-Grenze `2026-10-24T06:30:00Z`;
- null kostenpflichtige Requests.

Stage A untersuchte den vollständigen sichtbaren Index, fand 47 Textkandidaten und setzte AAPL
wegen des exakt per Feedkonfiguration belegten CIK und der passenden
Emittentenmeldung auf Rang 1. MUJ und MYN waren reine Texttreffer ohne passenden Ereignisbeleg. Das
ist ein realer Datenfluss und eine nachvollziehbare Kandidatengenerierung. Es ist kein unabhängiger
Recall-Nachweis: Der einzige aktive Newsfeed gehörte Apple und die Abfrage wurde nach Auswahl des
Feeds festgelegt. Der maschinenlesbare Bericht steht in
[research-v24-e2e.json](research-v24-e2e.json).

## Evidenz und Deduplizierung

Meldungen werden als `PRIMARY`, `SECONDARY` oder `COMMUNITY` gespeichert. Community-Inhalte können
keinen verifizierten Unternehmensfakt erzeugen. Cluster verwenden belegte Kennungen, Ereignisart,
36-Stunden-Fenster, Titelähnlichkeit und `origin_id`. Syndikationskopien behalten ihre URLs, zählen
aber nur einmal je Ursprung. Ähnliche Firmennamen erzeugen ohne eindeutigen Alias-/Kennungstreffer
keine Zuordnung.

`published_at`, `first_seen_at`, `retrieved_at`, `actual_event_at` und
`source_available_at` bleiben getrennt. Historische Abfragen sehen Identitäten, Fakten und
Meldungen erst ab ihrer belegten Verfügbarkeit. Spätere XBRL-Korrekturen bleiben durch die
V2.3-Regeln ausgeschlossen, bis ihre eigene Verfügbarkeit erreicht ist.

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
  --query 'new product' \
  --as-of 2026-10-24T06:30:00Z \
  --output reports/research-v24/report.json
```

Der Befehl führt keine Migration und keinen Netzwerkabruf aus. Er prüft den SEC-Rohdatenhash, baut
den Index atomar neu und erzeugt bei identischen Eingaben denselben Payload-Hash.

## Verbleibende Lücken

- EQS/GlobeNewswire benötigen einen belastbaren API-/Lizenzentscheid vor Integration.
- GDELT war während der realen Abnahme nicht verfügbar und liefert ohnehin nur Discovery-Metadaten.
- Ein Feed pro Emittent skaliert erst mit einem geprüften Feedkatalog und Update-Scheduler.
- Es fehlt ein vorab registrierter, ausreichend großer realer Teaserkorpus für Recall@10/50 und
  Top-1/Top-3. Die Metrikengine ist vorhanden; aktuelle Werte wären nicht belastbar.
- Kurs-, Volumen-, Liquiditäts-, Spread-, Bewertungs- und Analystendaten fehlen für Chancen-Signale.
- Für den realen RSS-Test ist vor produktiver Aktivierung eine abschließende rechtliche Prüfung der
  Metadatenspeicherung erforderlich.

Die Anwendung führt keine Trades aus und bezeichnet Scores weder als Wahrscheinlichkeit noch als
Kaufsignal.
