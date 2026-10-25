# V2.5.1 Provider-Audit

Stand: 24. Oktober 2026. Alle Preise und Grenzen müssen vor einer späteren Buchung erneut auf den
verlinkten offiziellen Seiten geprüft werden. Dieser PR hat keinen Tarif gebucht und keine
kostenpflichtige Anfrage ausgeführt.

| Anbieter | Offizieller Befund | Corporate Actions / Historie | Rechte und Budget | Entscheidung |
| --- | --- | --- | --- | --- |
| [Tiingo Pricing](https://www.tiingo.com/pricing) / [API-Dokumentation](https://www.tiingo.com/documentation/end-of-day) | Starter: 0 USD, 500 eindeutige Symbole/Monat, 50 Requests/Stunde, 1.000/Tag, 1 GB/Monat; 30+ Jahre EOD | EOD-Antwort enthält rohe/adjustierte OHLCV, `divCash` und `splitFactor` | Starter und Power sind laut Pricing „Internal Use Only“; keine Rohdatenweitergabe. Der kostenlose Zugang passt zum Pilotbudget. | **Erster US-Pilot**, weil ein Request je Symbol Preise und Actions gemeinsam liefert. |
| [EODHD Pricing](https://eodhd.com/pricing) / [Terms](https://eodhd.com/financial-apis/terms-conditions) | Free: 20 Calls/Tag, ein Jahr Historie; Demo-Schlüssel nur AAPL.US. Bezahlter EOD-Tarif bietet 30+ Jahre. | Splits/Dividenden sind separate Endpoints; Free-Zugriff laut Pricing auf ein Jahr und Aktivierung durch Support begrenzt. | Zehn Titel mit Preisen plus zwei Action-Endpunkten benötigen mindestens 30 Calls. Ein Paid-Tarif braucht separate Freigabe und kann mit Steuer/Währung die 20-EUR-Grenze überschreiten. | Bestehenden Adapter und Offline-Normalisierung behalten; **kein V2.5.1-Live-Pilot**. |
| [Twelve Data Pricing](https://twelvedata.com/pricing) / [Docs](https://twelvedata.com/docs) | Basic: 8 Credits/Minute, 800/Tag; freie Marktabdeckung ist auf drei Märkte bzw. Trial-Symbole begrenzt. | Preis-, Referenz-, Dividenden- und Split-Datasets werden angeboten; Plan-/Symbolzugriff muss praktisch geprüft werden. | Basic nennt interne Non-display-Nutzung. Der nächste Individualtarif liegt laut Pricing deutlich über 20 EUR/Monat. | Nur Audit; Adapter erst nach kostenlosem Feld-, Symbol- und Lizenztest. |
| [Alpha Vantage Support](https://www.alphavantage.co/support/) / [Docs](https://www.alphavantage.co/documentation/) | Free: 25 Requests/Tag. `TIME_SERIES_DAILY` liefert 25+ Jahre rohe OHLCV; Daily Adjusted enthält Adjusted Close, Splits und Dividenden. | Ein vollständiger Daily-Adjusted-Abruf kann die Pilotmenge grundsätzlich innerhalb des Tageslimits abdecken; Endpoint-/Outputsize-Verfügbarkeit ist mit eigenem Free-Key zu testen. | Kein Schlüssel war verfügbar. Speicherung, interne Nutzung und Weitergabe müssen vor einer Integration gegen die Terms geprüft werden. | Vergleichskandidat, **nicht implementiert**, bis Feld- und Rechteprüfung abgeschlossen ist. |

## Entscheidung

Tiingo gewinnt den kontrollierten US-EOD-Pilot technisch: vorhandener, geprüfter Collector; ein
Abruf je Titel; getrennte rohe und adjustierte Werte; Actions in derselben Antwort; ausreichend
großes kostenloses internes Kontingent. Der Pilot archiviert unveränderte Antworten mit SHA-256 und
gibt niemals API-Schlüssel weiter.

Die Entscheidung belegt keine vollständige Delisting-, MIC- oder offizielle Kalenderabdeckung.
Tiingo-EOD sind Composite-Preise und keine ausführbaren Börsenquotes. Bid/Ask, exakte
Handelssitzungen und historische Erstverfügbarkeit bleiben eigene Datenbedarfe. Providerangaben
werden nicht zu historischen Stammdatenbelegen hochgestuft.
