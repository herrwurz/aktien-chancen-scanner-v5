# V2.4 Quellen- und Kostenmatrix

Stand: 24.10.2026. „Öffentlich lesbar“ wird nicht als Erlaubnis für Massenerfassung oder
Weiterverteilung behandelt. Ohne eindeutigen API-/RSS- und Lizenzbeleg speichert V2.4 keine
Volltexte. Monatliches Zusatzbudget dieser Auswahl: 0 EUR.

| Quelle | Zugang und Felder | Historie / Limits | Rechte / Kosten | Aktienbezug und Qualität | Entscheidung |
|---|---|---|---|---|---|
| SEC EDGAR | offizielle JSON-Endpunkte für Ticker, Submissions, XBRL | historische Filings; faire Nutzung, User-Agent und begrenzte Rate | kostenlos; [SEC-Zugriffsregeln](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | CIK, Ticker, Accession; primär und zeitlich belastbar | vorhanden, weiterverwenden |
| GLEIF | offizielle REST-API, LEI-Rechtsträgerdaten | Versionen/Abrufzeiten; API-Limits beachten | kostenlos, CC0; [API](https://www.gleif.org/en/lei-data/gleif-api), [Nutzung](https://www.gleif.org/en/meta/lei-data-terms-of-use) | LEI/Name/Land; Identität, keine News | vorhanden, weiterverwenden |
| GDELT | DOC 2.0 JSON: URL, Titel, Domain, Sprache, Datum | präzise Zeitfenster, standardmäßig letzte drei Monate; kein garantierter Volltext | kostenloser offener Discovery-Dienst; Artikelrechte verbleiben bei Verlagen; [DOC API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/), [Daten](https://www.gdeltproject.org/data.html) | Entity-Mapping muss separat belegt werden; breit, aber noisig | **implementieren: Metadaten/Links** |
| Offizielle IR-Feeds | je Emittent RSS/Atom, Titel, Link, Zeit, GUID | feedabhängig; historische Tiefe meist klein | nur allowlisted Feed mit dokumentiertem `license_status`; keine Seitenumgehung | originäre Emittentenquelle, starke Zuordnung | **generischen Adapter implementieren** |
| EQS News | öffentliches Archiv/Newsfeed; Meldungen enthalten oft ISIN/WKN/LEI | gute DACH-Historie sichtbar; keine belegte freie Massen-API-/Rate-Regel | Newswire ist Distributionsprodukt; [Regulatory News](https://www.eqs.com/ir-services/regulatory-news), [EQS News](https://www.eqs-news.com/) | sehr wertvolle Primärmeldungen | später: schriftliche API-/Lizenzklärung |
| GlobeNewswire | offizielle RSS-Navigation und öffentliche Releases | internationale Historie; Limits nicht öffentlich belegt | API-/Wiederverwendungsrechte nicht als kostenlos belegt; [Website](https://www.globenewswire.com/), [Legal](https://www.globenewswire.com/legal) | originäre Pressemitteilungen, Emittentennamen | später: Feed-/Lizenzfreigabe klären |
| FinanzNachrichten.de | öffentliche Website/RSS-Hinweise | Historie sichtbar; keine dokumentierte freie Massen-API | automatisierte Speicherung/Weitergabe nicht belegt; [Website](https://www.finanznachrichten.de/) | gute DACH-Aktienzuordnung, sekundär/aggregiert | später prüfen; kein Scraper |
| finanzen.net | dokumentierte öffentliche RSS-Seite | aktuelle Metadaten, historische Garantie unklar | RSS-Lesbarkeit erlaubt keine Volltextarchivierung; [RSS](https://www.finanzen.net/dienste/rss), [AGB](https://www.finanzen.net/agb) | Tickerseiten, Sekundärmeldungen | später: nur Metadaten nach Rechteprüfung |
| wallstreetONLINE | einzelne Autoren-/Themen-RSS sichtbar | Historie/Rate nicht dokumentiert | automatisierte Massennutzung nicht belegt; [AGB](https://www.wallstreet-online.de/agb) | News plus Werbung/Foren erfordern Qualitätsfilter | später; kein Scraper |
| DER AKTIONÄR | Website/Newsletter | Teaserhistorie nicht als freie API belegt | keine zulässige systematische Volltexterfassung belegt; [Website](https://www.deraktionaer.de/) | wichtig für manuellen Teaserabgleich | ausschließen aus Auto-Collector, manuell prüfen |
| Deutsche Börse / Börse Frankfurt | Websites und kommerzielle Datenprodukte | hochwertige Markt-/Emittentendaten | maschinenlesbare Nutzung typischerweise Produkt/Lizenz; [Data Services](https://www.deutsche-boerse.com/dbg-en/our-company/know-how/data-services) | starke MIC-/ISIN-Zuordnung | später nach Preis-/Lizenzangebot |
| Nasdaq | Websites, Data Link und lizenzierte Datenangebote | datasetabhängig | freie Kontingente datasetabhängig, Newsrechte nicht pauschal; [Data Link](https://data.nasdaq.com/) | gute US-Zuordnung | später gezielt prüfen |
| Reddit | genehmigungspflichtige Data API | Limits/Retention vertragsabhängig | kommerzielle Nutzung kann kostenpflichtig sein; [Data API Terms](https://redditinc.com/policies/data-api-terms) | Community-Aufmerksamkeit, kein Faktenbeleg | später, nur zugelassene API/COMMUNITY |
| Stocktwits | Developer-Zugang nur als genehmigte API | Zugang und Limits an Anwendung gebunden | automatisiertes Scraping ausdrücklich untersagt; [Terms](https://stocktwits.com/about/legal/terms), [Developer](https://api.stocktwits.com/developers) | tickerbezogene Community-Daten | später, nur genehmigte API/COMMUNITY |
| Seeking Alpha | Website/RSS-Verweise, kommerzielle Lizenzen | Abdeckung gut, Zugriff häufig konto-/paywallgebunden | individuelle Nutzung; keine freie Massennutzung belegt; [Terms](https://about.seekingalpha.com/terms) | Analysen, sekundär | ausschließen innerhalb Budget |
| Benzinga | lizenzierte REST/TCP/RSS-News-API | Echtzeit und breite US-Coverage | kommerziell; Pro deutlich über Budget; [API](https://www.benzinga.com/apis/cloud-product/stock-news-api), [Preise](https://www.benzinga.com/pro/pricing) | tickerbezogen, schnell | ausschließen innerhalb Budget |
| MarketWatch / CNBC | öffentliche redaktionelle Seiten/Feeds | historische Tiefe vorhanden, API nicht belegt | keine freie Nachrichten-Massenlizenz belegt | guter Kontext, sekundär | ausschließen bis Lizenz/API belegt |

## Auswahl der ersten Integrationen

1. **GDELT-Metadaten**: kostenlos, dokumentierter JSON-Zugang, internationale Discovery. Es werden
   nur API-Metadaten, Hashes und Links archiviert; Treffer bleiben `SECONDARY/unknown`, bis eine
   Primärquelle sie bestätigt.
2. **Allowlisted RSS/Atom für offizielle Investor-Relations-Feeds**: originäre Meldungen und 0 EUR.
   Jeder Feed braucht einen expliziten Lizenzstatus und Unternehmensbeleg; ohne diese Konfiguration
   verweigert der Adapter den Abruf.
3. **Kein dritter neuer Provider in diesem PR**: EQS und GlobeNewswire wären fachlich besser als
   weitere Portale, aber ein kostenloser systematischer Zugriff samt Speicher-/Weitergaberechten
   ist nicht ausreichend belegt. Ein scheinbarer Scraper würde das Abnahmekriterium verletzen.

## Laufzeitstatus und Fehlergrenzen

Konfiguration und tatsächlicher Erfolg werden getrennt gezählt. Der Collector meldet
`configured_sources`, `successful_sources`, `unavailable_sources`, `fresh_sources` und
`stale_sources`. Ein einzelner Ausfall verwirft erfolgreiche Batches anderer Provider nicht.

GDELT wiederholt ausschließlich Transportfehler sowie HTTP 429, 500, 502, 503 und 504. Es gibt
höchstens einen Retry mit begrenztem Backoff; jeder Versuch belastet das explizite Requestbudget.
Nach Erschöpfung folgt `unavailable` mit `gdelt_retries_exhausted` und `fallback_used=false`.
