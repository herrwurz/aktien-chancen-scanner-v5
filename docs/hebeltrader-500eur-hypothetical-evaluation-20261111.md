# HEBELTRADER – 500-EUR-Modellkäufe: 42 Calls

**Stichtag:** 2026-11-11 · **Quelle:** [42 Register-Abschriften](hebeltrader-originalreports-42.json) · **Daten:** [vollständige Einzelberechnungen](hebeltrader-500eur-hypothetical-positions-20261111.json)

## Aussagegrenze

**Dies ist keine historische Performanceauswertung und kein echtes Depot.** Auf Nutzerwunsch wird unterstellt, dass jeder Call mit rund 500 EUR zum Register-Einstiegspreis gekauft worden wäre. Die vorliegenden Einstiegskurse sind **keine bestätigten Kaufabrechnungen**, und die Ziel- und Stoppmarken sind **nicht als historische Ausführungen belegt**. Die hypothetischen Szenarien dürfen nicht als realisierte Gewinne oder Verluste addiert werden.

## Rechenmethode

- Budget je Call: **500,00 EUR**; Stückzahl = `floor(500 / Einstiegspreis in EUR)`; keine Bruchstücke; Rest-Cash separat.
- **E =** ausdrücklich empfohlener Einstieg aus dem Register (20 Fälle). **I =** nur indikative Reportnotierung als ausdrücklich hypothetischer Proxy (22 Fälle). Ein fehlendes separates **Kauflimit** bleibt in allen Fällen fehlend.
- Währung und Kursnotierungen der Calls EUR; die angegebenen Aktienziele in USD oder EUR sind keine Derivate-Exitkurse.
- Keine Gebühren, Steuern, Bid-/Ask-Abschläge, Slippage, Limit-Nichterfüllungen, Liquiditäts- oder Währungseffekte eingerechnet. Die angegebenen Marken sind rein hypothetische Verkaufspreise.
- `Stopp1 voll`: alle Stücke exakt zu Stopp 1 verkauft. `Ziel1 → Einstieg`: floor(Stückzahl/2) zu Call-Ziel 1 verkauft, Rest exakt zum Einstandspreis. `Ziel1 → Ziel2`: Hälfte zu Ziel 1, Rest zu Ziel 2. Alle Varianten setzen erreichbare, ausführbare Quotes und die nötige zeitliche Reihenfolge **hypothetisch** voraus.
- Beim Einzel-Szenario für eine 500-EUR-Position: `Gewinn/Verlust = Summe der angenommenen Erlöse − Stückzahl × angenommener Einstieg`. Nicht investierter Budgetrest bleibt unberührt.

## Rechenprüfung aller 42 Annahmekäufe

| Größe | Wert |
|---|---:|
| Anzahl angenommener Calls | 42 |
| Nominelles Gesamtbudget | 21.000,00 EUR |
| Rechnerisch tatsächlich eingesetzte Mittel | 20.992,70 EUR |
| Unverwendete Budgetreste | 7,30 EUR |
| Szenario: **alle** fallen direkt auf Stopp 1 | -12.675,23 EUR |
| Szenario: **alle** erreichen Ziel 1, Rest zum Einstieg | 39.542,94 EUR |
| Szenario: **alle** erreichen Ziel 1 und Ziel 2 | 216.480,45 EUR |

Die letzten drei Zeilen sind **reine kontrafaktische Rechenbeispiele**, keine Schätzung der eintretenden Depotperformance. Die Ausgaben liegen zeitlich auseinander, einige Calls sind bereits abgelaufen. 21.000 EUR sind deshalb keine Aussage über den tatsächlich nötigen gleichzeitigen Kapitaleinsatz.

## Einzelpositionen: rein hypothetischer Gewinn/Verlust (EUR)

| Ausgabe | Basiswert | WKN | Einstieg € | Stück | Einsatz € | Kursart | Alle Stopp 1 | ½ Ziel1 + Rest Einstand | ½ Ziel1 + Rest Ziel2 |
|---|---|---|---:|---:|---:|:---:|---:|---:|---:|
| 22/25 | KION | MJ2DR6 | 0,31 | 1612 | 499,72 | I | -193,44 | 274,04 | 1.080,04 |
| 31/25 | Henkel Vz. | SU6X8P | 0,11 | 4545 | 499,95 | I | -272,70 | 545,28 | 2.681,90 |
| 34/25 | DHL Group | HD94XR | 0,092 | 5434 | 499,93 | I | -353,21 | 309,74 | 2.105,67 |
| 73/25 | Uber | MJ3CHB | 0,16 | 3125 | 500,00 | I | -343,75 | 312,40 | 2.094,22 |
| 74/25 | Amazon | SW979R | 0,32 | 1562 | 499,84 | I | -296,78 | 585,75 | 2.350,81 |
| 92/25 | Alphabet | SY0LMB | 0,12 | 4166 | 499,92 | I | -291,62 | 791,54 | 3.603,59 |
| 110/25 | Qualcomm | VG1YQN | 0,225 | 2222 | 499,95 | I | -211,09 | 1.138,77 | 4.788,41 |
| 158/25 | Thales | SX6DHJ | 0,5 | 1000 | 500,00 | I | -300,00 | 515,00 | 3.220,00 |
| 169/25 | Halliburton | UG4H12 | 0,065 | 7692 | 499,98 | I | -346,14 | 711,51 | 3.076,80 |
| 171/25 | Salzgitter | UG6WU7 | 0,43 | 1162 | 499,66 | I | -360,22 | 1.231,72 | 7.454,23 |
| 175/25 | Hannover Rück | MM3GW6 | 0,27 | 1851 | 499,77 | I | -277,65 | 758,50 | 3.860,60 |
| 176/25 | Schneider Electric | MK3C4P | 0,39 | 1282 | 499,98 | I | -307,68 | 685,87 | 3.512,68 |
| 179/25 | Gilead Sciences | FA8G3Q | 0,05 | 10000 | 500,00 | I | -370,00 | 900,00 | 6.400,00 |
| 198/25 | Mercedes-Benz | MM6ZLH | 0,42 | 1190 | 499,80 | I | -357,00 | 856,80 | 7.151,90 |
| 203/25 | TotalEnergies | MM7KAA | 0,33 | 1515 | 499,95 | I | -318,15 | 1.794,09 | 10.837,03 |
| 10/26 | Fraport | HT7GRA | 0,105 | 4761 | 499,91 | I | -357,08 | 916,29 | 5.285,43 |
| 46/26 | Air Liquide | MM51LF | 0,135 | 3703 | 499,91 | I | -296,24 | 805,18 | 4.314,72 |
| 81/26 | UnitedHealth | FD09J0 | 0,68 | 735 | 499,80 | I | -330,75 | 612,89 | 3.718,81 |
| 93/26 | Adidas | DU0UHF | 0,19 | 2631 | 499,89 | I | -315,72 | 1.578,00 | 8.710,72 |
| 137/26 | BASF | MJ7DUX | 0,07 | 7142 | 499,94 | I | -249,97 | 928,46 | 5.677,89 |
| 140/26 | Thales | DN3NVH | 0,3 | 1666 | 499,80 | I | -316,54 | 1.382,78 | 7.921,83 |
| 141/26 | Leonardo | VJ2RFH | 0,7 | 714 | 499,80 | I | -314,16 | 1.399,44 | 8.318,10 |
| 143/26 | Broadcom | MN8GZP | 0,59 | 847 | 499,73 | E | -211,75 | 803,70 | 4.564,58 |
| 144/26 | Pfizer | WA4R5Q | 0,175 | 2857 | 499,98 | E | -328,56 | 1.235,22 | 7.815,76 |
| 147/26 | KKR | VH62T5 | 0,19 | 2631 | 499,89 | E | -342,03 | 762,70 | 5.105,50 |
| 151/26 | SAP | UP9A9X | 0,14 | 3571 | 499,94 | E | -321,39 | 1.820,70 | 11.107,90 |
| 154/26 | Danaher | JY3SF7 | 0,22 | 2272 | 499,84 | E | -318,08 | 1.454,08 | 6.963,68 |
| 157/26 | Vertiv | HM4EB1 | 0,8 | 625 | 500,00 | E | -225,00 | 901,68 | 3.828,23 |
| 161/26 | UnitedHealth | VH2LU2 | 0,42 | 1190 | 499,80 | E | -309,40 | 1.237,60 | 6.866,30 |
| 173/26 | Micron | UN87G6 | 5,3 | 94 | 498,20 | E | -230,30 | 629,80 | 3.346,40 |
| 176/26 | Salesforce | JG0AEJ | 0,46 | 1086 | 499,56 | E | -314,94 | 933,96 | 5.223,66 |
| 192/26 | Costco | JY5SQZ | 0,16 | 3125 | 500,00 | E | -281,25 | 1.124,64 | 4.719,54 |
| 193/26 | JPMorgan Chase | MN6CYX | 0,42 | 1190 | 499,80 | E | -321,30 | 1.065,05 | 5.325,25 |
| 195/26 | Johnson & Johnson | JE11C1 | 0,36 | 1388 | 499,68 | E | -319,24 | 1.103,46 | 5.503,42 |
| 198/26 | SLB | VY95PV | 0,14 | 3571 | 499,94 | E | -321,39 | 1.053,15 | 4.714,45 |
| 199/26 | Nasdaq, Inc. | JY7FDN | 0,22 | 2272 | 499,84 | E | -318,08 | 681,60 | 3.896,48 |
| 200/26 | Analog Devices | MN84GA | 1,1 | 454 | 499,40 | E | -295,10 | 649,22 | 3.622,92 |
| 201/26 | Synopsys | MN9WA9 | 0,13 | 3846 | 499,98 | E | -269,22 | 788,43 | 3.961,38 |
| 202/26 | Deutsche Bank | WB14HL | 0,65 | 769 | 499,85 | E | -299,91 | 902,40 | 4.182,60 |
| 203/26 | American Electric | MN6D8E | 0,17 | 2941 | 499,97 | E | -294,10 | 1.058,40 | 4.985,97 |
| 204/26 | RTX | FE1C78 | 0,21 | 2380 | 499,80 | E | -261,80 | 1.178,10 | 6.449,80 |
| 210/26 | Amazon | HM55NU | 0,4 | 1250 | 500,00 | E | -312,50 | 1.125,00 | 6.131,25 |

## Was fehlt für wirkliche historische Performance?

1. **Tatsächliche Kaufzeitpunkte oder eine klar regelbasierte erste mögliche Kaufzeit** inklusive zeitgerechtem Briefkurs; eine Report-Indikation allein weist keine Ausführung nach.
2. **WKN-spezifische historische Geld-/Briefzeitreihen** und Stückquotierungen; Index-/Aktien- oder anderes Derivat dürfen nicht als Ersatz verwendet werden.
3. **Chronologischer Exit:** Zuerst Stop, Ziel 1, Ziel 2 oder zeitbasierter Exit, gegebenenfalls Teilverkauf nach Regel; Tages-OHLC allein kann die Intraday-Reihenfolge nicht sicher belegen.
4. **Gebühren und Wechselkurs** bei tatsächlicher Abrechnung; offene und ausgelaufene Positionen korrekt behandeln.

### Produktspezifische Recherche JY7FDN

An der Börse Stuttgart sind für JY7FDN die ISIN **DE000JY7FDN1**, **J.P. Morgan SE** als Emittent, 120 USD Strike, 0,1 Bezugsverhältnis und 19.03.2027 Bewertungstag beschrieben ([Stammdaten](https://www.boerse-stuttgart.de/en/products/leverage-products/warrants/stuttgart/jy7fdn/)). Diese Stammdaten ersetzen **keine** historischen, ausführbaren Kauf-/Verkaufskurse ab 27.10.2026. Tiingo beschreibt historische Aktien-Tageskurse, nicht dieselbe garantierte JY7FDN-Quote-Historie ([Dokumentation](https://www.tiingo.com/documentation/end-of-day)).

**Status:** Modellpositionen und mathematische Auszahlungsprofile für 42 Calls bereitgestellt; **0 historisch vollständig belegte Abschlüsse**. Keine Scanner-/Webentwicklung.
