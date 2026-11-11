# HEBELTRADER: historische Prüfung der 19 abgelaufenen Calls

Stichtag 11.11.2026. Budget 500 EUR je Call. **Keine belegte historische Wittmer-Gesamtrendite.**

Diese Tabelle zeigt Aktienbeobachtungen, keine Call-Verkäufe. Zielberührungen nach einem früheren Stopp sind keine gewonnenen Trades. Alle Datenreihen sind vorläufig; Kalender-Vollständigkeit und vollständiger Zweitquellenabgleich fehlen. „—“ bedeutet nur: in den abgerufenen Zeilen nicht beobachtet.

| Ausgabe | Aktie / Call | Aktienziel 1 | Aktienziel 2 | Aktienstopp 1 | Kurszeilen |
|---|---|---|---|---|---:|
| 22/25 | KION / MJ2DR6 | 2025-03-06 | 2025-08-07 | 2025-04-03 | 144 |
| 31/25 | Henkel Vz. / SU6X8P | — | — | 2025-03-12 | 200 |
| 34/25 | DHL Group / HD94XR | gesperrt | gesperrt | gesperrt | 130 |
| 73/25 | Uber / MJ3CHB | — | — | — | 153 |
| 74/25 | Amazon / SW979R | 2025-10-31 | — | — | 152 |
| 92/25 | Alphabet / SY0LMB | 2025-08-29 | 2025-09-18 | 2025-06-23 | 133 |
| 110/25 | Qualcomm / VG1YQN | 2025-10-27 | — | 2025-07-31 | 134 |
| 158/25 | Thales / SX6DHJ | — | — | 2025-12-02 | 132 |
| 169/25 | Halliburton / UG4H12 | 2026-01-05 | — | 2025-10-10 | 117 |
| 171/25 | Salzgitter / UG6WU7 | 2025-10-08 | 2026-01-07 | — | 115 |
| 175/25 | Hannover Rück / MM3GW6 | — | — | 2025-10-16 | 112 |
| 176/25 | Schneider Electric / MK3C4P | — | — | 2025-11-18 | 113 |
| 179/25 | Gilead Sciences / FA8G3Q | 2026-01-27 | — | — | 108 |
| 198/25 | Mercedes-Benz / MM6ZLH | — | — | 2026-03-19 | 89 |
| 203/25 | TotalEnergies / MM7KAA | 2026-02-12 | 2026-03-19 | — | 86 |
| 10/26 | Fraport / HT7GRA | — | — | 2026-05-05 | 103 |
| 46/26 | Air Liquide / MM51LF | gesperrt | gesperrt | gesperrt | 129 |
| 81/26 | UnitedHealth / FD09J0 | 2026-07-16 | — | — | 90 |
| 93/26 | Adidas / DU0UHF | — | — | 2026-07-30 | 80 |

DHL ist wegen 14 Zeilen mit identischen OHLC-Werten und fehlenden Volumenangaben vorläufig gesperrt. Air Liquide ist wegen der Kapitalmaßnahme und noch nicht freigegebener Anpassung der Originalmarken gesperrt. Einzelne fehlende/Null-Volumina stehen zusätzlich in results.json.

## Separates Szenario: bis zur Rückzahlung gehalten

Emittenten-Rückzahlungen sind belegt; Kauf zur Reportindikation und Halten ohne Stopp sind eigene Annahmen. Dies ist keine Simulation von Wittmers Strategie und kein realer Trade. Die Kostenvariante mit 5 EUR je Kauf/Rückzahlung ist nur eine Sensitivität, kein belegter Banktarif. Stückzahl wird innerhalb des 500-EUR-Budgets angepasst; Steuern nicht berücksichtigt.

| Ausgabe / Call | Rückzahlung je Stück | Stück ohne Gebühren | Gewinn ohne Gebühren | Gewinn bei 5 EUR je Vorgang |
|---|---:|---:|---:|---:|
| 169/25 / UG4H12 | 0.37 EUR | 7692 | 2346.06 EUR | 2312.57 EUR |
| 171/25 / UG6WU7 | 5.54 EUR | 1162 | 5937.82 EUR | 5871.61 EUR |

Die zwei Fälle sind eine selektive Teilmenge. Es wird daraus keine Trefferquote und kein 19- oder 42-Call-Gesamtergebnis berechnet.

## Reproduktion

`python research/hebeltrader-performance-20261111/reproduce.py --check` prüft Quellenhashes, Registerabgleich, Kursdaten und erzeugte Ergebnisse offline. Ohne --check werden results.json und RESULTS.md reproduziert.

Methodik, Quellenbewertung und konkrete Datenanforderungen: [README.md](README.md).
