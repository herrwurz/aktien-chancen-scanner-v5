# V2.5.2 – kurzfristige Aktien-Research-Kandidaten

V2.5.2 untersucht Aktien für einen Horizont von 1–20 Handelssitzungen. Der Lauf ist ein
deterministischer Research-Screen, kein Backtest, Handelssignal oder Auftrag. Er verwendet den
gemeinsamen Research-Index, bleibt aber fachlich vom HEBELTRADER-Detektiv getrennt.

## Datenfluss und Zeitgrenzen

Der Scanner öffnet das V2.5.1-SQLite-Archiv mit `mode=ro` und `query_only=ON`. Er enumeriert das
gesamte tatsächlich vorhandene Archiv und verbindet eine Zeile nur dann mit dem Research-Index,
wenn CIK/ISIN sowie vorhandener Ticker, Börsenplatz und MIC widerspruchsfrei passen. Ein Konflikt
ergibt `unavailable`; ähnlich aussehende Ticker werden nicht angenähert.

Für den ersten echten Pilot stehen zehn unabhängig aus dem SEC-Archiv ausgewählte Instrumente zur
Verfügung. Acht besitzen 250 archivierte Zeilen: FIVE, MPAA, LEGN, RFL, INVE, BGM, AAPL und NC.
PXED besitzt 58 Zeilen und fällt am Gate `insufficient_sessions` aus. VOGX besitzt wegen
`provider_data_error` keine Kursreihe und erscheint nur dann in einem Scannerbericht, wenn es im
Marktarchiv eine Listingzeile gibt; andernfalls bleibt es im V2.5.1-Coveragebericht dokumentiert.
Diese zehn Titel sind ein begrenzter Integrationspilot, keine Marktstichprobe und keine Grundlage
für Performanceaussagen.

Die Kursabfrage läuft in `modeled`. Die Sitzung und der modellierte Schlusszeitpunkt werden als
frühestmögliche Rechenverfügbarkeit verwendet. Weil die Daten erst 2026 lokal archiviert wurden,
ist damit keine historische Verfügbarkeit im Jahr 2025 belegt. Deshalb sind alle Resultate
`historical_availability_verified=false` und `training_eligible=false`.

## Merkmale, Gates und Bewertung

Alle Fenster enden am angegebenen `signal_date`. Spätere Bars werden vor jeder Berechnung
entfernt. Verwendet werden:

- adjustiertes Momentum über 5, 10 und 20 Sitzungen;
- Volumen der Signalsitzung geteilt durch den Mittelwert der 20 vorherigen Sitzungen;
- Median aus **Rohschluss × Rohvolumen in USD**, ATR(14), ATR-Prozent und Eröffnungslücke;
- SMA-5/SMA-20-Trend, Abstand zum vorherigen 20-Sitzungs-Hoch und optionaler Ausbruch;
- relative 20-Sitzungs-Stärke nur bei einem ausdrücklich angegebenen, belegten Benchmark-Archiv;
- belegte Nachrichten, deren Veröffentlichung und Quellenverfügbarkeit spätestens am Signalzeitpunkt
  liegen.

`PRIMARY`, `SECONDARY` und `COMMUNITY` bleiben getrennt. Community-Inhalte sind nur Kontext. Fonds,
nicht exakt aufgelöste Identitäten, weniger als 250 Sitzungen, veraltete Preise, unvollständige
OHLCV-Werte und unzureichende Liquidität fallen geschlossen aus. Fehlender Benchmark und fehlender
Kalender werden als Unsicherheit ausgewiesen.

Ein technischer Ausbruch, ungewöhnliches Volumen oder ein bestätigter Katalysator kann den Status
`candidate_research` auslösen. Ohne Auslöser lautet der Status `watch_only`; bei einem harten Gate
`unavailable`. Der ganzzahlige Score ist nur eine offen ausgewiesene Sortierregel. Er ist keine
Wahrscheinlichkeit.

Ein SEC-Aktieneintrag mit `instrument_type=unknown` wird technisch ausgewertet, bleibt jedoch
unabhängig vom Trigger `watch_only` und trägt `instrument_type_unverified`. Eine Freigabe als
`operating_company` erfolgt ausschließlich über die optionale Datei
`PILOT_DIR/instrument-reviews.json` mit CIK/Ticker, Originalquelle, Quellen-SHA, Abrufzeitpunkt,
Reviewer und Reviewzeitpunkt. Fonds und als `other` belegte Instrumente bleiben ausgeschlossen.

Das ATR-Szenario nennt Referenzkurs, modellierten Stopp, Ziel und Brutto-CRV. Da Tiingo-EOD keine
ausführbaren Bid-/Ask-Quotes liefert, bleiben `spread_status=unavailable`, `net_crv=null` und
`executable=false`. Die ausgewiesene Kostenannahme wird nicht in ein scheinpräzises Netto-CRV
umgerechnet.

Momentum, ATR und Breakout werden auf der für Corporate Actions vergleichbaren adjustierten Skala
berechnet. Der angezeigte Referenzkurs ist dagegen der Rohschluss der Signalsitzung. ATR-Abstände
werden mit dem Verhältnis Rohschluss/adjustierter Schluss auf dieselbe Rohpreisskala transformiert,
bevor Stopp und Ziel modelliert werden. Die Felder `reference_price_basis`, `feature_price_basis`
und `raw_per_adjusted_scale` machen diese Umrechnung prüfbar. Sie bleibt ausdrücklich
nicht ausführbar.

`signal_date` im Berichtsheader ist der angeforderte Stichtag. Pro Titel stehen der tatsächlich
verwendete letzte Sitzungstag, `market_data_cutoff_at` und `data_age_calendar_days`. Nachrichten
werden höchstens bis zum modellierten beziehungsweise kalenderbelegten Schluss dieser Sitzung
zugelassen; eine Meldung nach Börsenschluss kann kein Signal derselben Schlusskerze auslösen.

## Offline-Lauf auf dem Hetzner-Archiv

Nach Checkout des Feature-Branches läuft der Scan ohne Netzwerk, Compose, PostgreSQL oder Secret:

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/short-term-candidates-v2-5-2
git worktree add --detach /opt/scanner-v252 \
  origin/feat/short-term-candidates-v2-5-2
cd /opt/scanner-v252
PILOT_DIR=/opt/scanner-v251-tiingo-pilot \
OUTPUT_DIR=/opt/scanner-v252-opportunities \
SIGNAL_DATE=2025-12-31 \
bash scripts/run-opportunity-dry-run.sh
```

Der Pilotordner wird read-only eingebunden. Der neue Ordner enthält `opportunities.json`,
`opportunities.csv` und `opportunities.sha256`. Vor Auswertung ist zu prüfen, ob `2025-12-31`
tatsächlich die letzte gewünschte gemeinsame Signalsitzung ist. Der Befehl beeinflusst Immich und
Produktivdatenbanken nicht.

Vor dem Containerstart validiert der Runner `coverage.sha256` und bindet `coverage.json` an den
logischen SHA des SQLite-Archivs. `PILOT_DIR` und `OUTPUT_DIR` dürfen weder identisch noch ineinander
verschachtelt sein. PXED und VOGX bleiben dadurch auch dann im Quellen-Audit sichtbar, wenn sie
nicht als vollständig analysierbare Archivinstrumente vorliegen.

Der Scanner akzeptiert den Pilotbericht nur mit `coverage_kind=real_provider_archive` und
`real_provider_coverage_measured=true`. Der Analyse-Cutoff `as_of` wird deterministisch aus dem
letzten lokalen Speicherzeitpunkt des unveränderlichen Archivs gelesen (`archive-latest`) und nicht
aus der aktuellen Systemuhr erzeugt. Derselbe Archiv-/Index-/Signalstand liefert daher wieder
denselben JSON- und CSV-Inhalt.

Der reale Dry-run wurde in der Codex-Arbeitsumgebung nicht ausgeführt, weil das lizenzgebundene
Tiingo-Archiv nur auf Hetzner liegt. Erfolgreiche Offline-Fixtures werden nicht als reale Abnahme
ausgegeben.

## Offene Datenfragen

- **PXED:** 58 beobachtete Providerzeilen beweisen weder die Ursache noch eine lückenlose frühere
  Historie. Listingbeginn, Symbolhistorie und gewünschtes Fenster müssen anhand einer Primärquelle
  geprüft werden.
- **VOGX:** Der Providerfehler belegt keine Nichtnotierung. SEC-Identität, historisches
  Providersymbol und Listingzeitraum müssen vor einem neuen, ausdrücklich autorisierten Request
  geprüft werden.
- **Handelskalender:** Die offiziellen Feiertags- und Early-Close-Veröffentlichungen der jeweiligen
  Börse können als Quellen dienen, müssen aber für den benötigten Zeitraum archiviert, lizenziert
  und in die vorhandene SHA-gebundene Kalenderdatei übertragen werden. Ein Softwarekalender oder
  die vorhandenen Kursdaten allein belegt keine historische Vollständigkeit.
- **Inkrementelle Aktualisierung:** Das V2.5.1-Archiv fügt neue Sitzungen idempotent ein und bewahrt
  erkannte Revisionen. Für einen Betrieb ist zusätzlich ein festes Korrekturfenster erneut
  abzurufen; dessen Requestverbrauch und jede geänderte Revision müssen berichtet werden.
- **Universum:** Nach dem Acht-Titel-Pilot wird das verfügbare SEC-Universum in unabhängigen,
  vorab festgelegten Batches erweitert. Auswahl nach später bekannten Gewinnern ist unzulässig.

V2.5.3 beginnt erst nach ausreichender Kalender-, Benchmark-, Delisting-, Kosten- und
Point-in-Time-Coverage. Es friert Regeln und Schwellen vor einem unangetasteten Out-of-sample-
Fenster ein und führt einen Schlusskurshinweis frühestens zur nächsten belegten Sitzung aus.
