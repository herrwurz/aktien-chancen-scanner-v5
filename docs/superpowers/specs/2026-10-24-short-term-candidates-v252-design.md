# Scanner V6 V2.5.2 – kurzfristige Research-Kandidaten

## Ziel und Abgrenzung

V2.5.2 erzeugt transparente Research-Kandidaten für einen Horizont von 1–20 Handelssitzungen.
Es verwendet den gemeinsamen V2.4-Research-Index und das append-only V2.5.1-Kursarchiv, erzeugt
aber weder Orders noch freigegebene Kaufsignale oder Gewinnwahrscheinlichkeiten. Der
HEBELTRADER-Detektiv bleibt ein getrenntes Entscheidungsmodell. V2.5.3-Backtesting gehört nicht
in diesen PR.

Der reale V2.5.1-Pilot ist `partial`: acht Titel besitzen 250 Sitzungen, PXED besitzt 58 und VOGX
keine importierte Reihe. Das reicht für einen ausdrücklich begrenzten, offline/read-only
Research-Dry-run. Es reicht nicht für Marktcoverage, validierte historische Signalgüte oder einen
Backtest. Die Archivierung am 25. Oktober 2026 belegt keine lokale Verfügbarkeit der Kurse im Jahr
2025. Deshalb läuft die Demonstration ausschließlich als `modeled` und bleibt
`historical_availability_verified=false` sowie `training_eligible=false`.

## Architektur

- `scanner/opportunities/models.py`: strikte Feature-, Risiko-, Kandidaten- und Coverage-Verträge.
- `scanner/opportunities/features.py`: ausschließlich vergangenheitsgerichtete technische
  Berechnungen aus sortierten, abgeschlossenen Sitzungen.
- `scanner/opportunities/catalysts.py`: point-in-time verfügbare PRIMARY-/SECONDARY-Evidenz;
  COMMUNITY ist nur Zusatzkontext und niemals bestätigter Unternehmensfakt.
- `scanner/opportunities/short_term.py`: harte Daten-Gates und deterministisches Ranking.
- `scanner/opportunities/report.py`: kanonische JSON-/CSV-Ausgabe und SHA-256-Sidecar.
- `scanner/opportunities/cli.py`: read-only Dry-run über alle tatsächlich im Archiv vorhandenen
  Instrumente; keine feste Watchlist und kein Provider-Netzwerkzugriff.

Das Universum ist die Schnittmenge aus belegten Research-Identitäten und vorhandenen
Kursarchiv-Listings. Die Architektur verarbeitet beliebig viele archivierte Titel inkrementell;
die acht Reihen sind nur die erste reale Stichprobe. Eine spätere Erweiterung lädt unabhängig
ausgewählte Titel innerhalb des kostenlosen Tiingo-Kontingents nach und darf nicht nach
nachträglicher Rendite auswählen.

## Zeit- und Preismodell

Alle Features für Sitzung `t` verwenden höchstens Daten bis zum Schluss von `t`. Baselines
schließen den jeweils untersuchten Zielwert aus, wenn dies fachlich erforderlich ist:

- Momentum 5/10/20: adjustierter Schluss `t` gegen `t-n`;
- Volumenratio: adjustiertes Volumen `t` gegen den Mittelwert der 20 vorherigen Sitzungen;
- Medianumsatz: Median aus adjustiertem Schluss × adjustiertem Volumen der letzten 20 Sitzungen;
- ATR(14): True Range der letzten 14 abgeschlossenen Sitzungen mit dem vorherigen adjustierten
  Schluss;
- Gap: adjustierte Eröffnung `t` gegen adjustierten Schluss `t-1`;
- Trend: SMA(5) gegenüber SMA(20) und Richtung des 20-Sitzungen-Momentums;
- Distanz/Breakout: Schluss `t` relativ zum Hoch der 20 vorherigen Sitzungen;
- relative Stärke: 20-Sitzungen-Rendite des Titels minus die gleich berechnete Rendite eines
  separat belegten Benchmark-Instruments. Ohne Benchmark bleibt das Feld `unavailable`.

Adjustierte OHLCV dienen den technischen Reihen, damit belegte Splits nicht als Momentum-, Gap-
oder Volumenereignis erscheinen. Rohschluss und Adjustierung bleiben im Ergebnis getrennt
sichtbar. Fehlende adjustierte OHLCV-Werte werden nicht ergänzt.

## Daten-Gates und Status

Harte Gates für den realen Pilot-Dry-run:

- exakte Research-/Archividentität und operative Aktie, kein belegter Fonds;
- mindestens 250 Sitzungen für `candidate_research` oder `watch_only` im Pilot;
- vollständige adjustierte OHLCV-Werte für alle benötigten Lookbacks;
- positiver Medianumsatz und ausreichende Aktualität relativ zum angeforderten Signalstichtag;
- keine Identitäts- oder Providerkonflikte.

Ein Verstoß ergibt `unavailable`. Ein technisch auswertbarer Titel erhält `candidate_research`,
wenn ein vorab definiertes Preis-/Volumenereignis oder ein rechtzeitig belegter Katalysator
vorliegt und keine wesentliche Unsicherheit das Setup sperrt. Sonst lautet der Status
`watch_only`. Fehlender Benchmark oder Kalender bleibt als Unsicherheit sichtbar und wird nicht
als positiver oder negativer Fakt erfunden. Ein hoher Score ist keine Wahrscheinlichkeit.

## Katalysatoren

Unterstützt werden belegte Prognoseänderungen, Ergebnisse, Übernahmen, Großaufträge,
Produktzulassungen, Partnerschaften und Analystenrevisionen. Primärmeldungen und regulatorische
Dokumente sind `PRIMARY`, redaktionelle Einordnungen `SECONDARY`, Community-Inhalte `COMMUNITY`.
Ein Katalysator zählt nur, wenn sein belegter Veröffentlichungs-/Verfügbarkeitszeitpunkt nicht
nach der untersuchten Sitzung liegt. Unbelegte oder verspätete Meldungen bleiben `unknown`.

## Ranking und Risikomodell

Das Ranking kombiniert dokumentierte Punkte für Momentum, Trend, Volumenereignis, Breakout,
Katalysatorqualität, Liquidität und Datenvollständigkeit. Hohe ATR-Prozente, veraltete Daten und
fehlende optionale Belege erzeugen nachvollziehbare Abzüge oder Unsicherheiten. Gleichstände
werden stabil nach kanonischer Asset-ID gebrochen.

Das Risikomodell zeigt ein nicht ausführbares Research-Szenario: Referenzschluss, ATR-basierte
Invalidierung, ATR-basiertes Ziel und Brutto-CRV. Ohne beobachtete Bid-/Ask-Quotes bleibt Spread
`unavailable`; konservative Kosten werden als Annahme separat ausgewiesen. Netto-CRV bleibt ohne
belastbare Quote `null`. Kein Feld behauptet eine tatsächlich ausführbare Transaktion.

## Bericht und Abnahme

JSON und CSV enthalten Identität, Handelsplatz, Referenzkurs/-datum, Featurewerte, Auslöser,
Katalysatoren und Quellen, Risiken, Datenvollständigkeit, Status, Scorebegründung, Coverage und
SHA-256. Der Dry-run berichtet untersuchte gegenüber im Index vorhandenen Unternehmen,
ungeeignete Titel, Staleness, Fehler, Signalhäufigkeit, Providerrequests und Kosten.

Regressionstests prüfen insbesondere:

- kein Kurs nach dem Signalzeitpunkt und korrekte Lookback-Grenzen;
- Split-/Dividendenbehandlung über adjustierte versus rohe Daten;
- fehlende Sitzungen und unvollständige Providerwerte;
- veraltete Kurse, Fonds-/Aktienfilter und Identitätskonflikte;
- unzureichende Liquidität und fehlende Nachrichtenbelege;
- Ranking-Gleichstände und reproduzierbare Scores/Artefakte;
- fehlende Quote sperrt ausführbares Netto-CRV;
- `strict` kann 2025 keine damals lokal verfügbare Reihe aus dem 2026-Archiv behaupten;
- der reale Dry-run bleibt als begrenzte Stichprobe und hypothetische Feature-Demonstration
  gekennzeichnet.

Ein offizieller Handelskalender, Delisting-/Survivorship-Abdeckung und belastbare historische
Verfügbarkeitsmethodik bleiben Voraussetzungen für V2.5.3.
