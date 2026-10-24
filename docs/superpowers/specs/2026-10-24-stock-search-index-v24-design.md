# Scanner V6 V2.4 – Intelligenter Aktien-Suchindex und Candidate Retrieval

## Ziel und Grenze

V2.4 ersetzt die V2.3-Hashstichprobe für die produktive Kandidatensuche durch einen vollständig
durchsuchbaren, versionierten lokalen Index des jeweils belegten Universums. Die Stichprobe bleibt
nur als unabhängiger Regressionstest erhalten. Der Index dient dem HEBELTRADER-Detektiv und dem
Aktien-Chancen-Scanner über gemeinsame Recherche-Schnittstellen; beide Anwendungen behalten eigene
Ranking- und Entscheidungslogik. V2.4 erzeugt keine Kaufentscheidung.

## Architekturentscheidung

Für die erste reale Datenbasis mit rund 8.000 SEC-Emittenten wird **SQLite mit FTS5** verwendet.
Der Index wird offline in eine neue Datei gebaut, geprüft, mit SHA-256 manifestiert und danach per
atomarem Dateitausch schreibgeschützt veröffentlicht. Das passt zum leseintensiven Betrieb, erlaubt
Point-in-time-Abfragen, verursacht keine laufenden Kosten und benötigt keine produktive
PostgreSQL-Migration. FTS5 deckt Namen, Aliase, Geschäftsbeschreibungen und Meldungstexte ab;
B-Tree-Indizes bedienen CIK, Ticker, Land, SIC und Zeitgrenzen.

PostgreSQL wird erst neu bewertet, wenn ein reproduzierbarer Benchmark mindestens eines zeigt:
mehrere notwendige gleichzeitige Schreiber, verteilte API-Instanzen ohne gemeinsam verfügbares
Indexartefakt, ein Indexartefakt über 10 GiB oder p95 über 500 ms für Stage-A-Abfragen auf der
Zielhardware. Die bestehende PostgreSQL-Datenbank bleibt unberührt.

## Datenmodell und Point in time

Tabellen im versionierten SQLite-Artefakt:

- `issuer`: stabile interne ID, Name, CIK und belegter Herkunftsmarkt.
- `issuer_alias`: Alias, Typ, Quelle, `source_available_at`, Gültigkeitsgrenzen.
- `listing_version`: Ticker, Börse/MIC, ISIN/WKN soweit belegt, Land, Währung sowie Gültigkeit.
- `classification_version`: SIC-Code und SEC-Bezeichnung mit Quelle und Verfügbarkeit.
- `document`: Accession/Quell-ID, Ereignisart, Veröffentlichung, Acceptance, Abruf, SHA und URL.
- `fact_observation`: Kennzahl, Wert, Einheit, Periode, Accession, Revision und Verfügbarkeit.
- `event`: belegte Ereignisaussage, Fundstelle, Verifikationsstatus und Zeitpunkte.
- `price_coverage`: Provider- und Zeitraum-Metadaten; keine erfundenen oder ersetzten Kursreihen.
- `issuer_fts`: FTS5-Projektion von Name, Alias, belegter Geschäftstätigkeit und Dokumenttext.
- `index_build`: Schema-/Parser-Version, Rohquellen-SHAs, Zeilenanzahlen, Erstellzeit und Payload-SHA.

Jede historische Abfrage verlangt `as_of`. Sichtbar sind nur Datensätze mit
`source_available_at <= as_of` und mit damals gültiger Identitätsversion. Ein korrigierter XBRL-Wert
ersetzt den früher sichtbaren Wert erst ab dem Acceptance-/Verfügbarkeitszeitpunkt der Korrektur.
Abrufzeit und rekonstruierte historische Verfügbarkeit bleiben getrennt. SEC-SIC dient als grobe,
belegte Vorauswahl und wird nie als vollständige Geschäftsbeschreibung ausgegeben.

## Gemeinsame Schnittstellen

`scanner/research_index/protocols.py` definiert typisierte, paginierte Read-only-Methoden:

- `research.universe(as_of, market, cursor, limit) -> UniversePage`
- `research.candidates(query, as_of, limit<=50) -> CandidateBatch`
- `research.events(asset_id, as_of, cursor, limit) -> EventPage`
- `research.fundamentals(asset_id, as_of, metrics) -> FundamentalSet`
- `research.prices(asset_id, as_of) -> PriceCoverage`
- `research.coverage(as_of) -> CoverageReport`

Jede Antwort enthält Index-Build-ID, Quellenstatus, Datenalter, erfasste/gesamte Titel, Märkte,
Kosten und Auslassungszählungen. API-Antworten enthalten begrenzte Belegausschnitte; vollständige
Dokumente verbleiben im SHA-geprüften Archiv.

## Zweistufige Suche

Stage A normalisiert strukturierte Teaser-Hinweise und bildet eine Vereinigung mehrerer
Retrieval-Kanäle: SIC/Land/Größe, FTS-BM25 über Namen und Geschäftstätigkeit, historisch sichtbare
Kennzahlen und Ereignisse. Jeder Kanal liefert eine Reserve; eine deterministische Fusion bewertet
bestätigt, widerlegt und unbekannt getrennt. Bis zu 50 verschiedene Kandidaten gehen in Stage B.
Sind keine belegten, indexierbaren Einschränkungen vorhanden oder bleibt die Vorauswahl zu breit,
lautet der Status `insufficiently_constrained`; es wird keine scheinpräzise Top-3 erzeugt.

Stage B lädt für alle bis zu 50 Kandidaten zeitgültige Detailbelege, prüft positive und negative
Hinweise sowie Widersprüche und erzeugt danach maximal drei Kandidaten. Unbekannte Merkmale sind
neutral. Das Top-3 wird erst nach der vollständigen Stage-B-Bewertung gebildet. Eine ausreichend
breite Reserve je Retrieval-Kanal verhindert, dass ein einzelner früher BM25- oder SIC-Fehler den
richtigen Titel ausschließt.

## Qualität und Abnahme

Ein unveränderliches Evaluationsmanifest trennt echte historische Fälle von synthetischen
Funktionsfällen und wird vor Indexaufbau registriert. Lösungen dürfen nicht in Watchlists oder
Queries eincodiert werden. Berichtet werden Recall@10/50 der Stage A, Top-1/Top-3 der Stage B,
Enthaltungsquote, Out-of-index-Verhalten, PIT-Verstöße, Feld- und Marktcoverage, p50/p95-Laufzeit,
maximale Antwortgröße, Netzwerkrequests und Kosten. Zielwerte für den ersten SEC-Build:

- 100 % des erfolgreich archivierten SEC-Universums indexiert oder jede Auslassung ausgewiesen.
- Keine Evidenz nach `as_of` in historischen Tests.
- Recall@50 >= 0,90 und Recall@10 als Baseline-Bericht auf einem vorab fixierten echten Korpus;
  kein Freigabeanspruch, solange das Korpus zu klein für eine belastbare Aussage ist.
- Top-3 und Top-1 getrennt ausweisen; keine unkalibrierten Wahrscheinlichkeiten.
- 100 % Enthaltung für absichtlich unzureichende und nicht erfasste Fälle.
- Stage-A-p95 <= 500 ms auf dokumentierter Hetzner-Vergleichshardware, Antwort <= 256 KiB.
- Zusätzliche Provider-/KI-Kosten <= 20 EUR/Monat; SEC/GLEIF-Pfad 0 EUR.

## Quellenabdeckung

SEC EDGAR und GLEIF bleiben erhalten. SEC deckt US-Filer, regulatorische Dokumente und begrenzte
XBRL-Fakten ab, aber keine vollständigen Nachrichten oder historische Wertpapierstammdaten. GLEIF
liefert CC0-Rechtsträgeridentität, keine Börsennachrichten. Für DE/AT/CH/EU wird im PR ein
quellenbezogenes Entscheidungsprotokoll gepflegt. Unternehmensregister, Börsen-/Emittentenportale
oder weitere Adapter werden erst implementiert, wenn Massenabruf, historische Zeitstempel,
Nutzungsrechte und Kosten schriftlich belegt sind. Bis dahin weist Coverage diese Märkte als nicht
abgedeckt aus.
