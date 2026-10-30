# 27er-Referenz: PIT-Diagnose (2026-10-30), ohne Retuning

Quelle: `reference-27-evaluate-pit.json` nach Paid-EODHD-Freeze (`150d8562…`).

## Kennzahlen (unverified hypotheses)

| Kanal | suggestion_cases | Top1 | Top3 | Top8 | graded |
|---|---:|---:|---:|---:|---:|
| Offline (Sektor) | 17 | 2 | 4 | 6 | 25 |
| Market (Chart PIT) | 26 | 2 | 2 | 5 | 25 |

Beide Kanäle sind **keine** Identifikationen. Evidenz-Scanner bleibt bei 0 Treffern ohne Quellenpakete.

## Beobachtungen

- Market deckt 26/27 Fälle ab; HT-016 ohne `publication_date` → kein PIT.
- Gemeinsame Treffer nur teilweise (z. B. HT-003 offline+market Top1).
- Viele historisch „correct“ Fälle ohne Offline-/Market-Treffer: Chart/Sektor allein reichen nicht.
- Keine Algorithmusänderung aus diesen Entwicklungsfällen ableiten.

## Nächster produktiver Schritt

Auflösung Blind 202/26 nach Report-Kauf dokumentieren (Position in structure/market), ohne Nachziehen.
