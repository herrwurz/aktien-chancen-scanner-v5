# HEBELTRADER – Bestands- und Qualitätsprüfung

Stand: 11.11.2026. Quellen: PDF-Inventar (31.10.), Call-Auswahl-Korpus, Fallregister auf main. Aus den vorhandenen Metadaten erzeugt; **keine erneute Prüfung der privaten PDF-Bytes**.

| Messwert | Anzahl |
|---|---:|
| PDF-Inventareinträge | 133 |
| Einmalige PDF-SHA-256 | 131 |
| Unterschiedliche PDF-Ausgaben | 131 |
| Call-Korpus-Einträge | 134 |
| Originalreport-Abschriften im Register | 42 |
| Vereinigung unterschiedlicher Ausgaben | 136 |
| Registerfälle mit gesondert belegtem empfohlenem Einstieg | 20 |
| Registerfälle ohne solchen Einstieg | 22 |
| Registerfälle mit ausdrücklich ausgewiesenem Kauflimit | 0 |

**Nicht mit einer Veröffentlichungs-Gesamtzahl gleichsetzen:** Sammlung selektiv; fehlende Nummern nur anhand eines offiziellen Ausgabenkatalogs als echte Lücke einstufen. Der ältere 118er-V2.1-Prüflauf und dessen Feldquoten sind keine aktuelle 136er-Validierung.

## Nicht in beiden älteren Quellen

- Nur Call-Korpus oder Fallregister ohne PDF-Inventar: 119/25, 199/26, 203/26, 204/26, 210/26.
- Kein Eintrag im Call-Korpus, aber anderswo dokumentiert: 204/26, 210/26.
- Identische PDF-Hashes bei mehrfacher Inventarerfassung: 93/26 und 95/26. Als Dateinamen-Aliase erhalten, nicht als mehrere Ausgaben zählen.

## Quellenwidersprüche (keine automatische Korrektur)

| Ausgabe | Typ | Call-Korpus | PDF-Inventar |
|---|---|---|---|
| 15/25 | wkn_role_or_extraction | SX04FN | A0X9EJ |
| 16/25 | wkn_role_or_extraction | SX04B8 | 590900 |
| 24/25 | wkn_role_or_extraction | SJ9Z8M | 633500 |
| 2/26 | publication_date | 2025-01-08 | 2026-01-08 |
| 3/26 | publication_date | 2025-01-09 | 2026-01-09 |
| 4/26 | publication_date | 2025-01-12 | 2026-01-12 |
| 39/26 | publication_date | 2023-03-09 | 2026-03-09 |
| 61/26 | wkn_role_or_extraction | UQ2KJ7 | 850628 |

Weitere offene Felder: Emittenten, ISIN, historisch belegte Handelsplätze, Veröffentlichungsuhrzeiten (PDF-`Stand` ist nur ein Guess), die fehlenden empfohlenen Einstiege und sämtliche tatsächlichen Transaktionsbelege. Bei WKN-Widersprüchen ausdrücklich Aktien-WKN und Derivat-WKN gegen die Originalseite abgleichen. Zeitstempel mit unplausiblem Jahr oder Sommerzeit-Offset vor Backtests sperren.

## Ergebnisstand

Es gibt **keine nachgewiesene historische Gesamtrendite der Calls**. Historische Modell-/synthetische Backtests und dokumentierte Teaser-Treffer dürfen nicht als realisierte Trades gezählt werden. Historische Bid-/Ask- und Ausführungsdaten sowie die PDF-Reverifizierung sind weiter offen. Das Fallregister bleibt maßgeblicher Arbeitsstand; bei Widerspruch gilt der Originalreport.

## Nächste Prüfungen

1. Fehlende und kollidierende Ausgaben mit echten Original-PDFs und SHA prüfen.
2. Alle 42 Register-Abschriften gegen PDF-Seite 1–3 vergleichen; Korrekturen als eigenes, datiertes Review festhalten.
3. Ausgaben 199/26 zuerst ohne Renditebehauptung als Pilot prüfen.
4. Echte Bid-/Ask-Historien und Handelsbelege gesondert beschaffen; erst dann Performanceberechnungen freigeben.
