# HEBELTRADER – historisches Auswertungsschema (V1)

Stand: 11.11.2026. **Dokumentation und Vorbereitung, keine verifizierte Renditeberechnung.** Original-PDF hat bei Widerspruch Vorrang. Dieser Stand führt keine Scanner-, Web- oder Serverfunktionen ein.

## Quellenklassen und Priorität

1. Originalreport: PDF-SHA-256, Ausgabe, Ausgabedatum, konkrete Seite und wörtliches Feld; nur nach tatsächlichem PDF-Abgleich `pdf_verified`.
2. Fallregister-Abschrift: `register_transcription_not_pdf_reverified`; Angaben und Währungen unverändert lassen.
3. Identitätsrecherche / historische Marktdaten: nur mit Quellenlink, Zeitpunkt, Markt/MIC, Anpassungssemantik, Archivhash und Verwendungsrechten.
4. Modellannahme: separater Datensatz mit Versionsnummer, Ausführungsregel und Reviewer; niemals zurück in Originalfelder schreiben.
5. Tatsächliche Transaktion: Beleg mit Ausführungszeit, Stückzahl, Kurs, Währung, Gebühren, Teilverkäufen und Ausstiegen; keine Umdeutung einer Kursindikation in eine Ausführung.

## Datengrenzen und Nullzustände

`not_stated` = nicht im Original ausgewiesen; `not_transcribed` = noch nicht erfasst; `conflicting` = widersprüchliche Quellen; `not_applicable` = fachlich nicht zutreffend; `unverified` = ohne ausreichenden Beleg. Das leere separate Kauflimit ist **nicht** der empfohlene Einstieg. Eine fehlende explizite Empfehlung darf nicht aus einer Indikation abgeleitet werden. Drei Tabellen der Originalcall-Sammlung sind als separate JSON-Datei abgebildet. Report-Szenariogewinne und CRV sind Verlagsangaben, keine Erträge.

## Vier voneinander getrennte Auswertungen

**A Teaseridentifikation:** Zeitlich eingefrorenen Ersttipp gegen späteres, belegtes Original prüfen; richtig/falsch/offen. Keine nachträgliche Verbesserung, kein ungeprüfter Trefferquoten-Nenner. Entwicklungsfälle und unabhängig blind getestete Fälle getrennt berichten.

**B Aktienkurs-Ereignisse:** Nach belegter Veröffentlichung und erstem zulässigem Handel Kursziel- und Stoppberührungen anhand historischer OHLC-Daten ermitteln; OHLC sagt nichts über tatsächliche Ausführung. Bei simultaner Ziel-/Stoppberührung unklare Reihenfolge (konservative Bandbreite statt eindeutiger Treffer). Splits, Währung, Kalender, Dividenden und Delisting gesondert prüfen. Keine stillschweigende Exit- oder Einstiegserfindung.

**C Optionsschein-Simulation:** Nur mit verifizierter Produkt-WKN/ISIN, Bezugsverhältnis, Strike, Laufzeit, Emittentenbedingungen und zeitgerechten Bid-/Ask-Snapshots. Modellierter Einstieg zum Brief und Verkauf zum Geld, quotierte Größe/Liquidität und Ausfallzeiten prüfen. Slippage und Gebühren getrennt. Ohne diese Daten `not_evaluable`; eine Black-Scholes-Schätzung ist ein hypothetisches Szenario, kein verifizierter Backtest.

**D Tatsächlich ausgeführte Trades:** Ausschließlich durch Ausführungsbelege. Pro Teilverkauf Stückzahl und Nettoerlös; offener Rest bleibt offen. `net_realized_pnl = sum(sell_quantity * sell_price - sell_fees) - allocated_purchase_costs - allocated_buy_fees`; Währungsumrechnung mit belegten Ausführungs-/Abrechnungsdaten. Rendite = realisierter Nettogewinn / zugeordnete Anschaffungskosten einschließlich Gebühren. Offene Positionen getrennt nach Menge und Bewertungsstichtag ausweisen; keine erfundene Realisierung.

## Reproduzierbare Ausgabe

Jeder Lauf veröffentlicht: `as_of`, `method_version`, Git-Commit und Original-/Quell-SHAs, Anzahl im Universum, Anzahl verwendbarer Fälle, Anzahl offener und blockierter Fälle, genaue Ausschlussgründe sowie pro Fall Ereignisse, Orderregeln, Kosten, Ausführungsannahmen und Prüfstatus. Marktbeobachtungen, Verlagsprognosen, Modellrechnungen und Echtgeld-Trades niemals aggregiert vermischen. Teaser-Erfolge nach *vor Auflösung archivierten* Ersttipps, ausgeführte Trades nach echten Buchungen.

## Pilot 199/26

Nasdaq Inc., Call JY7FDN: Originalmarken aus Register-/PDF-Seitenhinweisen übernehmen, explizites Kauflimit offen. Vor Simulationsfreigabe: Originalseiten erneut verifizieren, Zeitpunkt der tatsächlichen Verfügbarkeit prüfen, historische handelbare Geld-/Briefpreise plus Liquidität und Produktbedingungen beschaffen. Bis dahin nur Sollmarken- und Aktienereignisprüfung mit entsprechendem Evidenzstatus.

## Keine Seiteneffekte

Keine privaten PDF-Bytes und keine Volltexte im Git; keine API-Token, Datenbankmigrationen, Scanner, Weboberflächen oder Orderfunktionen. Diese Dateien sind ein prüfbarer Dokumentationsstand, kein Live-Backtest.
