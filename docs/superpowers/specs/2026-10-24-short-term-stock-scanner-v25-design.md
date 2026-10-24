# Scanner V6 V2.5 – Kurzfristiger Aktien-Chancen-Scanner

## Ziel und Grenze

V2.5 findet unabhängig von HEBELTRADER beobachtenswerte Aktien für einen Horizont von 1–20
Handelstagen. Es verwendet den V2.4-Research-Index, erzeugt aber ein eigenes Strategiemodell.
Ergebnisse sind Research-Kandidaten, keine Orders und keine Kaufversprechen. Unvollständige
Preis-, Volumen-, Spread- oder Identitätsdaten verhindern ein freigegebenes Signal.

## Gemeinsame und getrennte Komponenten

Gemeinsam bleiben `research.universe`, `research.events`, `research.fundamentals`,
`research.prices` und `research.coverage`, Provenienz, Point-in-time-Grenzen und SHA-Archive. Neu
entstehen `scanner/opportunities/short_term.py`, `scanner/opportunities/features.py` und
`scanner/opportunities/backtest.py`. Der Detektiv rankt Teaserübereinstimmung; V2.5 rankt
Katalysator, Handelbarkeit, relative Stärke und Risiko. Scores oder Entscheidungen werden nicht
zwischen beiden Anwendungen übertragen.

## Datenvertrag

Jede Beobachtung benötigt Instrumentidentität, MIC, Börsenzeitzone, Handelswährung,
Sessiondatum, `available_at`, OHLCV, Adjustierungsstatus, Quelle, Abrufzeit und Rohdaten-SHA.
Corporate Actions werden separat gespeichert; Roh- und adjustierte Reihen dürfen nicht vermischt
werden. Quote-Daten enthalten Bid, Ask und Zeitpunkt. Fehlen echte Quotes, wird der Spread als
`unavailable` geführt und nicht aus OHLCV erfunden.

Nachrichten behalten Ereignis-, Veröffentlichungs-, Erstfund-, Abruf- und Revisionszeit. Ein
Katalysator zählt nur, wenn er vor der Signalerzeugung verfügbar war. Community-Aufmerksamkeit ist
ein eigener, höchstens unterstützender Faktor und kann keinen Unternehmensfakt bestätigen.

## Providerentscheidung innerhalb 0–20 EUR pro Monat

| Quelle | Mögliche Nutzung | Budget-/Rechtebefund | Entscheidung für V2.5 |
|---|---|---|---|
| bestehender EODHD-Adapter | globale EOD-OHLCV, Splits, Dividenden | Free-Kontingent beziehungsweise günstiger Plan; Preis, Umsatzsteuer, Delisting-Abdeckung und interne Nutzung vor Buchung erneut anhand [Pricing](https://eodhd.com/pricing) und [Terms](https://eodhd.com/financial-apis/terms-conditions) prüfen | erster kontrollierter Pilot, keine Buchung im PR |
| bestehender Tiingo-Adapter | US-EOD-OHLCV und Corporate Actions | Free-Zugang für begrenzte interne Forschung; bezahlter Individualplan kann oberhalb des Budgets liegen; [Pricing](https://www.tiingo.com/about/pricing), [Terms](https://app.tiingo.com/tos) | US-Vergleichsprovider, keine öffentliche Rohdatenweitergabe |
| Twelve Data | globale OHLCV/Metadaten | Free-Kontingent, kostenpflichtige Pläne und externe Anzeige gesondert lizenzieren; [Pricing](https://twelvedata.com/pricing) | späterer Adapter nach Feld-/Lizenztest |
| Alpha Vantage | begrenzte tägliche US-Zeitreihen | Free-Rate klein, DACH/Redistribution nicht ausreichend; [Dokumentation](https://www.alphavantage.co/documentation), [Terms](https://www.alphavantage.co/terms_of_service) | nur Vergleichstest |
| Marketstack | EOD/Intraday je Tarif | möglicher Tarif innerhalb Budget, aber Corporate Actions, Delistings und Anzeige-/Speicherrechte vorab prüfen; [Pricing](https://marketstack.com/pricing), [Agreement](https://marketstack.com/agreement) | Kandidat, noch nicht aktivieren |
| Stooq | CSV-Zeitreihen | kein hinreichend klarer offizieller API-/Weiterverwendungsbeleg und keine garantierten Corporate Actions | nicht automatisieren |
| Deutsche Börse/Börse Frankfurt | hochwertige DACH-Markt- und Quote-Daten | historische/redistributierbare Pakete voraussichtlich außerhalb des Budgets; [Data Services](https://www.deutsche-boerse.com/dbg-en/our-company/know-how/data-services) | Blocker für echte DACH-Spreads dokumentieren |

Keiner der bislang belegten Zugänge garantiert im Budget historische Bid/Ask-Reihen und
vollständige delistete Titel. V2.5 darf deshalb EOD-basierte Forschung ausführen, aber keine
intraday ausführbare Rendite behaupten. Jede externe Aktivierung braucht eine separate Kosten- und
Lizenzfreigabe.

## Merkmale und Auswahl

Das Universum wird zuerst nach verifizierter Aktienidentität, Mindesthistorie, Preis,
Dollar-/Euro-Umsatz und Datenalter gefiltert. Fonds und sonstige Instrumente laufen in getrennten
Universen. Merkmale werden ausschließlich aus zum Signalzeitpunkt verfügbaren Daten berechnet:

- Katalysatoralter und Evidenzklasse;
- 5-/10-/20-Tage-Rendite sowie relative Stärke gegen Markt und Branche;
- Volumenverhältnis gegen eine ausschließlich vergangene 20-Sitzungen-Basis;
- ATR und Gap-Risiko;
- Medianumsatz, Quote-Spreads soweit beobachtet und Handelssitzungsabdeckung;
- Widersprüche, Revisionen und Quellenlücken.

Ein Kandidat benötigt mindestens einen belegten Katalysator oder ein klar definiertes
Preis-/Volumenereignis, ausreichende Liquidität und vollständige Risikodaten. Fehlende Pflichtfelder
erzeugen `unavailable`; knappe oder widersprüchliche Evidenz erzeugt `watch_only`.

## Einstieg, Risiko und CRV

Das Signal entsteht nach Abschluss der auslösenden Sitzung und wird frühestens zur nächsten
zulässigen Sitzung bewertet. Einstieg ist der nächste beobachtbare Preis gemäß festgelegtem
EOD-Modell; Intraday-Hoch/Tief dieser Sitzung darf die Entscheidung nicht beeinflussen. Stopp und
Ziel werden vor dem Einstieg aus ATR beziehungsweise belegten technischen Marken festgelegt.

Das Netto-CRV verwendet explizite Provision, Spreadannahme und Slippage. Ohne Quote wird ein
separates konservatives Kostenband ausgewiesen. Berühren Tageshoch und Tagestief Ziel und Stopp,
gilt konservativ der Stopp zuerst. Positionen laufen höchstens 20 Handelstage; Kalender- und
Handelstage bleiben getrennt.

## Backtest und Abnahme

Zeitlich geordnete Walk-forward-Fenster trennen Merkmalsentwicklung, Schwellenwahl und Test. Keine
zufällige Zeilenaufteilung, nachträgliche Universumsbereinigung oder rückwirkende Revision. Delistete
Titel und Corporate Actions müssen enthalten oder als Coverage-Lücke quantifiziert werden.

Verglichen wird gegen Buy-and-hold des passenden Marktindex, eine einfache 20-Tage-Momentumregel
und eine zufällige, liquiditätsgematchte Auswahl. Kennzahlen: Coverage, Trefferquote, Nettoertrag,
Maximum Drawdown, erwarteter Wert, Haltedauer, Turnover, Kostenanteil, Fehlalarme, verpasste Chancen
und Stabilität je Walk-forward-Fenster.

Der erste PR implementiert Provider-Audit und unveränderliche Preisarchive. Der zweite ergänzt
Merkmale und Dry-run-Ranking. Erst ein dritter PR führt den historischen Walk-forward-Test aus.
Automatische Orders bleiben ausgeschlossen.
