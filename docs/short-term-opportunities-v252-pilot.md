# V2.5.2 – realer Hetzner-Dry-run

Stand: 25. Oktober 2026. Der Nutzer führte Commit `3a96fe9` isoliert auf dem vorhandenen
V2.5.1-Tiingo-Archiv aus. Der Container hatte `--network none`, das Quellverzeichnis war read-only,
und weder PostgreSQL noch Immich wurden verwendet.

## Integrität und Aufwand

- Signalstichtag: `2025-12-31`
- Modus: `modeled_research`
- Laufzeit einschließlich Containerstart: 3 Sekunden
- Providerrequests des ursprünglichen Piloten: 10
- Requests des V2.5.2-Dry-runs: 0
- Kosten: 0 EUR
- V2.5.1-Coverage-SHA:
  `fe243a487153ed89e5a019bb4df1216c5abd8259e75abe84c8dd4b66d824576f`
- Marktarchiv-SHA:
  `28f6c27fea7e6da5af1863a167311a0d87607f98e0fe302a5092de3a0613290f`
- finales JSON:
  `9dd5d854a47b2ec5a21ad0023200bca738f6b79b5f79ce5a8aea897ac0d43046`
- finale CSV:
  `cfdce9d16042ace93ad908cfc0159b5bd20637b80f8fe91ad7408ed9fc1f7940`
- `opportunities.json: OK`; `opportunities.csv: OK`

Lizenzierte Kursrohdaten und der vollständige Bericht bleiben unter
`/opt/scanner-v252-opportunities-p0` auf dem Server.

## Tatsächliche Coverage

| Kennzahl | Wert |
| --- | ---: |
| sichtbare SEC-Identitäten | 4.949 |
| archivierte Instrumente | 9 |
| konfliktfrei zugeordnet | 9 |
| technisch analysiert | 8 |
| `candidate_research` | 0 |
| `watch_only` | 4 |
| `unavailable` | 5 |
| zu geringe Liquidität | 4 |
| weniger als 250 Sitzungen | 1 |

Die Archivabdeckung des sichtbaren Index beträgt rund 0,182 Prozent. Das ist eine reale
Integrationsstichprobe und keine US-Marktabdeckung. Der V2.5.1-Quellpilot bleibt `partial`: neun von
zehn Instrumenten wurden importiert; PXED besitzt 58 Sitzungen und VOGX lieferte einen
`provider_data_error`.

## Watchlist und Ausschlüsse

| Rang | Ticker | Score | Befund |
| ---: | --- | ---: | --- |
| 1 | FIVE | 6 | positives 5/10/20-Momentum, aber kein Breakout oder Volumenimpuls |
| 2 | MPAA | 2 | Volumenratio 2,261; negatives 5/10/20-Momentum |
| 3 | LEGN | 1 | kein Trigger; 20-Sitzungs-Momentum etwa −18,5 % |
| 4 | AAPL | 0 | kein Trigger; 20-Sitzungs-Momentum etwa −5,0 % |

NC, INVE, RFL und BGM wurden wegen unzureichender Roh-USD-Liquidität ausgeschlossen. PXED wurde
wegen unzureichender Historie ausgeschlossen. VOGX besitzt keine importierte Kursreihe.

Alle vier Watchlisttitel bleiben durch `instrument_type_unverified`, `benchmark_unavailable` und
`calendar_unverified` begrenzt. Ein SEC-Listing allein bestätigt den Instrumenttyp nicht. MPAA wird
deshalb trotz realem Volumenimpuls nicht zum Kandidaten hochgestuft.

## Abnahmeurteil

**Kein belastbares Signal.** Es wurde kein positives Ergebnis erzwungen. Der Lauf belegt die reale,
reproduzierbare Verarbeitung des vorhandenen Archivs und die konservative Enthaltung bei fehlenden
Identitäts-, Kalender- und Benchmarkbelegen. Für einen praktisch marktbreiten aktuellen Scanner
fehlen weiterhin mindestens 100 ausreichend vollständige Aktienreihen, ein belegter US-Kalender,
ein separat geführter Benchmark, verifizierte Instrumenttypen und aktuelle News-Coverage.
