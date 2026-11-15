# Historische HEBELTRADER-Auswertung, 11.11.2026

**Status: Recherche und erste historische Aktienbeobachtungen durchgeführt; die historische Call-Strategierendite bleibt für alle 19 abgelaufenen Fälle nicht auswertbar.** Die übrigen 23 Fälle sind im 42er-Ledger enthalten, aber in diesem ersten Recherchepaket noch nicht historisch untersucht. Kein Fall erhält durch fehlende Daten eine Rendite von null. Die 500-EUR-Annahme ist kein Kaufbeleg.

## Konkrete Ergebnisse

[RESULTS.md](RESULTS.md) enthält die vorläufig beobachteten Aktienziel-/Stoppdaten für die abgelaufenen Calls. [results.json](results.json) enthält alle 42 Fälle und ihre getrennten Statuswerte, Quellen, Sperren und Berechnungen. Die 19 Kursreihen wurden tatsächlich abgerufen und numerisch archiviert; sie sind keine synthetischen Daten. Einzelne Kursfelder wurden unabhängig verglichen: Amazon am 31.10.2025 gegen StatMuse sowie Halliburton und Salzgitter am 18.03.2026 gegen die Emittentenfeststellungen. Alle drei Prüfungen stimmen in den geprüften Preisfeldern überein. Das validiert nicht die vollständigen Reihen.

Besonders relevant: Bei Alphabet, Qualcomm und Halliburton wird der Aktienstopp in den abgerufenen Daten **vor** dem ersten Aktienziel beobachtet. Eine spätere Zielberührung wäre kein Nachweis eines erfolgreichen Trades. Bei KION wird Ziel 1 vor dem ursprünglichen Stopp beobachtet; ohne Callkurse und Gültigkeit der damaligen Regeln lässt sich auch daraus kein regelgerechter Gewinn ableiten. Bei Uber liegt das höchste beobachtete Tageshoch knapp unter 102 USD; es wird nicht zum erreichten Ziel aufgerundet.

Zwei öffentlich dokumentierte UniCredit-Rückzahlungen ermöglichen separate Gegenrechnungen: UG4H12 0,37 EUR und UG6WU7 5,54 EUR pro Stück. Diese Resultate gehören ausdrücklich in **Halten bis Rückzahlung**, nicht in Wittmers Strategieauswertung. Eine vorherige Stopp-/Zeitregel könnte das Halten verhindert haben. Kein Gesamtgewinn aus diesen zwei selektiven Fällen wird auf das Universum übertragen.

## Autorität und unveränderte Originaldaten

Ausgangsstand auf `main`: Commit `3bc4b9a` (PR #147). Das Fallregister `docs/hebeltrader-identification-rules.md` bleibt maßgeblich. `reproduce.py` gleicht alle 42 Call-WKNs, Laufzeitangaben, Callmarken, Basispreise, Aktien-WKNs und Aktienmarken zwischen Register und strukturierter Abschrift ab. Originalreports hätten Vorrang, konnten hier aber nicht erneut gelesen werden: Es liegen im Checkout keine entsprechenden Original-PDFs vor. Ihre Hashes und Seitenverweise bleiben im bestehenden Originaldatensatz erhalten. Es wurden keine Originalwerte korrigiert.

Bei allen 19 abgelaufenen Calls ist der ausdrücklich empfohlene Einstieg in der Abschrift leer. Der Modellkauf verwendet deshalb die damalige **Reportindikation als Ersatzannahme**, nicht als belegten Briefkurs. Die 20 ausdrücklich erfassten Einstiege betreffen andere Fälle im 42er-Bestand.

## Vier getrennte Ergebnisse

| Klasse | Stand dieses Laufs |
|---|---|
| Historische ausführbare Call-Strategie | 0 von 19 auswertbar; PnL/Rendite `null` |
| Hypothetischer Modellpreisverlauf | Nicht berechnet: historische Bedingungen, Anpassungen und Volatilitätsverläufe fehlen |
| Historische Aktienbeobachtungen | 19 importierte Reihen; 17 vorläufig verglichen, DHL und Air Liquide gesperrt |
| Reale Trades | Keine Ausführungsbelege als Input; keine Rendite berechnet |
| Separates Halten-bis-Rückzahlung-Szenario | Zwei Fälle mit belegtem Rückzahlungswert, angenommenem Kauf und angenommener Haltedauer |

„Ausführbar“ benötigt zeitgerechte Bid/Ask-Kurse, zugehörige Quotierungsgrößen, Produktidentität und Handelsbedingungen. Echte Trades benötigen Abrechnungen. Ein offizieller Rückzahlungswert ist dagegen eine belegte Zahlung je gehaltenem Stück, kein Beweis für den Kauf oder ein Halten durch den Nutzer.

## Kursdaten, Zeitfenster und Validierungsgrenzen

- Quelle und Abrufzeit, Währung, Provider-Metadaten, Dateihash und Corporate Actions stehen pro Serie in [market-sources.json](market-sources.json). Symbolzuordnung im Skript: Xetra für deutsche, Paris für französische Aktien, US-Notierungen in USD. Die ursprünglichen Kurs-/Währungsangaben werden nicht umgerechnet.
- Der Veröffentlichungstag wird wegen unbekannter Veröffentlichungsuhrzeit vollständig ausgeschlossen. Beobachtungsbeginn ist die erste abgerufene Zeile danach, Ende der im Report angegebene Bewertungstermin. Das ist eine offengelegte Beobachtungsannahme, kein nachgewiesener Einstiegstag. Ereignisse am Veröffentlichungstag bleiben damit bewusst unbewertet.
- `first_observed_touches` ist das erste Datum **innerhalb der archivierten Zeilen**. Ziel/Stopp werden unabhängig betrachtet; keine Position, Stoppnachführung oder Teilverkäufe werden aus Aktien-OHLC konstruiert. Bei gleichen Ereignistagen wäre deren intraday Reihenfolge unbekannt.
- OHLC und `close` sind laut Yahoo splitbereinigt; `adjusted_close` enthält weitere Dividendenanpassungen und wird nicht als Trigger verwendet. Nichtadjustierte Originalmarken dürfen bei Kapitalmaßnahmen nicht unmittelbar mit rückwirkend adjustierten Preisen verglichen werden.
- Air Liquide: Quelle der Gesellschaft belegt Gratisaktien 1:10 und Zuteilung 10.06.2026; Yahoo führt die Anpassung am 08.06.2026. Der Produktanbieter zeigt für MM51LF einen angepassten Strike 190,9091 statt der ursprünglichen 210 EUR. Originalmarken bleiben unverändert; ohne historische Anpassungsmitteilung werden Ereignisse gesperrt. Ex- und Zuteilungstag sind unterschiedliche Daten.
- DHL: 14 der 130 Zeilen besitzen identische OHLC-Werte, teilweise fehlen Volumina. Eine verlässliche erste Intraday-Berührung lässt sich damit nicht behaupten; vorläufig gesperrt. Weitere einzelne Nullvolumina sind in den Fallwarnungen sichtbar.
- Kalender-Vollständigkeit, Börsenplatzidentität über die gesamte Historie und sämtliche Kapitalmaßnahmen wurden noch nicht unabhängig freigegeben. Es wird keine vollständige Negativaussage „Ziel niemals erreicht“ aus einer leeren Ereigniszelle abgeleitet.
- Die numerischen Daten sind hier für die angeforderte Auswertung archiviert. Eine allgemeine Datenvertriebs-/Weiterveröffentlichungslizenz der Anbieter ist nicht geprüft; das Paket ist kein Marktdatenfeed.

## Rechercheprotokoll und Zugangsgrenzen

[research-log.json](research-log.json) enthält 19 WKN-Suchen und je WKN mindestens einen Nachlauf, Suchanfragen, gefundene URLs sowie Extraktionsversuche. Suchtreffer werden nicht automatisch zu Belegen. Keine Such-Snippets, laufenden Aktienindikationen oder heutigen Quotierungen wurden als historische Bid/Ask-Reihe importiert. Die Abwesenheit von Suchtreffern beweist nicht, dass beim Emittenten oder kostenpflichtigen Anbieter keine Daten existieren.

[evidence.json](evidence.json) enthält konkrete Quellenbefunde, Rückzahlungen, Kapitalmaßnahme und Zugangsfehler. Yahoo-Chart-API antwortete auf query1 und query2 mit HTTP 429; die HTML-Tabellen waren über Extraktion zugänglich. Stooq lieferte HTTP 200 mit Browserprüfung statt CSV und wurde verworfen. Der Stuttgart-MM6ZLH-Link leitete auf eine allgemeine Seite weiter. GOYAX führte auf eine Such-/Listenseite. UniCredit zeigt für die zwei Produkte Rückzahlungsinformationen, aber keine zugängliche Historie. Bei GS stehen leere Rückzahlungsfelder; ein Strich wird **nicht** als Null interpretiert. Such-Snippets nennen dort teilweise um einen Tag abweichende Laufzeitdaten; extrahierte Produktseiten stimmen in den hier geprüften Fällen mit dem Report-Bewertungstag überein. Bewertung, letzter Handel und Rückzahlung sind nicht gleichzusetzen.

## Wittmers Regeln: weshalb keine erfundenen Verkäufe entstehen

Die vollständig erfassten Anlagegrundsätze stammen aus **199/26, Seite 6**, veröffentlicht nach dem Verfall dieser 19 Calls. Sie sind ein belegter Recherchehinweis, noch keine nachgewiesene historische Regelversion für alle älteren Ausgaben. Für jeden Fall fehlen seine damalige Seite mit Anlagegrundsätzen und gegebenenfalls spätere Management-/Updatehinweise.

Die beabsichtigte Ereignissimulation braucht danach:

1. Tatsächliche Reportverfügbarkeit, zulässigen Produkt-Handelsbeginn und Einstiegskontrolle (Aktienabstand zum Stopp, Ziel 1 bereits erreicht) bestimmen. Hypothetischen Kauf zur vorgegebenen Reportmarke getrennt von einer tatsächlich erreichbaren Ask-Ausführung halten.
2. Mit historischen Bid-Quotierungen den initialen Call-Stopp und belegte Trigger prüfen. Verkauf nicht automatisch zum Stoppwert: Bei Kurslücke ist der nächste verfügbare Geldkurs maßgeblich. Kein Tageshoch des Basiswerts als Callziel behandeln.
3. Bei belegtem Ziel-1-Trigger 50 Prozent verkaufen, Ganzzahlrundung ausdrücklich festlegen (Modellkonvention: abrunden; Rest bleibt in Position), Reststopp ab dem belegten Wirksamkeitszeitpunkt anheben.
4. Die 20-Handelstage-Regeln anhand des zutreffenden historischen Produktkalenders berechnen; Kontrollzeitpunkt für Verlustregel und Vorrang bei gleichzeitigem Ziel/Stopp aus Originalen klären. „Spätestens“ darf nicht rückwirkend zur günstigsten Ausstiegswahl werden. Eine fest gewählte Ausführung am Stichtag wäre gesonderte Modellannahme.
5. Jede Ausführung mit Zeit, Preisart, Quelle, Menge, Gebühren und Regelgrund protokollieren. Fehlende oder widersprüchliche Zeitreihen sperren den konkreten Strategieverlauf. Aktien-, Call-, Modell- und reale Ergebnisse bleiben getrennt.

Hier werden diese Voraussetzungen nicht durch eine Scheinsimulation ersetzt. Es gibt weder synthetische Bid/Ask-Kurse noch geschätzte Verkaufsdaten. Auch Black-Scholes wäre mangels historischer IV- und Produkthistorie derzeit keine belastbare Rekonstruktion.

## Budget und Kosten

Je Fall stehen unabhängig 500 EUR zur Verfügung; es wird kein simultaner Kapitalbedarf von 21.000 EUR oder Reinvestment unterstellt. Stückzahl = `floor((500 - Kaufgebühr) / angenommener Kaufpreis)`. Restgeld bleibt uninvestiert. Zahlungsbeträge werden je Vorgang kaufmännisch auf EUR-Cent gerundet (ROUND_HALF_UP); Preise je Schein dürfen Bruchteile eines Cents enthalten. Ohne Gebühren muss die bestehende 42er-Modellstückzahl exakt reproduziert werden.

Die Rückzahlungsszenarien verwenden 0 EUR bzw. hypothetisch je 5 EUR für Kauf und Rückzahlung; die Gebührensensitivität verändert auch die gekaufte Stückzahl. Die Rückzahlungsgebühr ist eine reine Kostenannahme, kein Nachweis einer tatsächlich verrechneten Gebühr. PnL = Stückzahl × Rückzahlung − Stückzahl × Kaufpreis − Kaufgebühr − Rückzahlungsgebühr. Rendite hier auf das 500-EUR-Budget. Keine Steuern, keine angenommene Broker-FX-Gebühr. Ohne zeitgerechte Quotes keine separat schätzbaren historischen Spreads oder Slippage.

## Was zur vollständigen Call-Auswertung konkret noch fehlt

Für die 19 WKNs in RESULTS.md: historische Produktbedingungen einschließlich Anpassungen und letzter Handelstag; historische Bid/Ask-Zeilen mit Zeitzone, Markt/Emittent und Quotegröße vom zulässigen Einstieg bis zum regelbedingten Ausstieg; historischer Handelskalender; die jeweils gültigen Reportregeln samt Updates. Einzelne Schlusskurse könnten eine Näherung ermöglichen, aber keinen belegten Intraday-Stoppbacktest. EODHD/Tiingo-Zugänge oder historische Exporte wurden in dieser Sitzung nicht bereitgestellt; es wurde kein kostenpflichtiger Kauf veranlasst.

Für reale Trades zusätzlich: tatsächliche Kauf-/Verkaufszeit, Stück, Kurs, Gebühren und Abrechnung. Die Nutzerannahme „je 500 EUR gekauft“ bleibt eine Modellvorgabe. Die 23 noch laufenden Calls müssen anschließend gesondert bis zum Stichtag und mit offenem Restbestand untersucht werden; sie zählen nicht als Verluste oder als erledigt.

## Offline-Reproduktion und Prüfungen

```sh
python research/hebeltrader-performance-20261111/reproduce.py
python research/hebeltrader-performance-20261111/reproduce.py --check
python -m unittest discover -s research/hebeltrader-performance-20261111 -p 'test_*.py' -v
```

Nur Python-Standardbibliothek, keine Datenbank, Scanneränderung, Weboberfläche oder Deployment. Eingabe- und Datenhashes sowie Ausgangscommit stehen im Ergebnis. Ein erneuter Webabruf kann wegen geänderter Websites andere Daten liefern; die veröffentlichte Berechnung läuft deterministisch auf den archivierten Zahlen. Änderungen an diesen Daten verlangen neue Hashes und erneute Ergebnisgenerierung.
