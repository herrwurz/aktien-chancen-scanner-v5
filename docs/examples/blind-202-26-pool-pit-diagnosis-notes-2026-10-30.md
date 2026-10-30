# Blind 202/26 – Pool-PIT Post-hoc (ohne Retuning)

Freeze und Fehlerklasse **A_universe** bleiben unverändert. Dies ist eine Nachdiagnose
auf dem Remap-Pool-PIT (`snapshots-pit-pool-v1-remap-2026-10-30`).

## Ergebnis

| Frage | Antwort |
|---|---|
| DBK im Pool-PIT? | Ja (`DBK.XETRA`, coverage 981) |
| In Pool-Market-Top-8? | **Nein** |
| `match_score` | **10** (Rang ~622 / 1053) |
| Namen mit Score 23 | **112** |
| Residualklasse | **B_chart_rank** (Universumslücke geschlossen) |

Features as_of 2026-10-30: `above_gd200=true`, aber `above_gd50=false`, `breakout=false`,
`gd200_rising=false`, `return_1y_pct=-0.7`. Clue `above_gd200` allein reicht bei ~1000
Kandidaten nicht für Top-8 — viele Namen treffen das volle Chart-Muster (Score 23).

Top-8 der Diagnose: APA, A, AI.PA, APD, ALLFG.AS, MO, AMGN (doppelt durch Pool+Overlay).

## Regeln

- Kein Score-/Filter-Retuning für diesen Blindfall.
- Nächster Hebel: Evidenz-Kanal (Quellenpakete), nicht Chart-Nachziehen.
- Duplikate im Pool+Overlay separat bereinigen (Follow-up, kein 202/26-Gewinnerfix).

Artefakte: `blind-202-26-diagnosis-pool-pit.{json,md}`, `blind-202-26-pool-pit-posthoc.json`.
