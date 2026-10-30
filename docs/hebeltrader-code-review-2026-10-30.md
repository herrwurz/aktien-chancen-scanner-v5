# Code-Review: HEBELTRADER-Stand auf `main` (2026-10-30)

Frühere Agenten-PRs (#26 Diagnose/US-Seed) sind verworfen bzw. nicht gemerged und
werden hier nicht fortgeführt. Bewertet wird ausschließlich der Copilot-Stand auf
`main` (Tip: `ea52ab6`, inkl. PR #50).

## Was das System ist

Primäres Ziel: aus anonymen HEBELTRADER-Teasern die Aktie finden (Top-3-Hypothese).
Pfad: Web-UI `/` → `investigate` / `reference_scan` → eingefrorenes Ranking → später
Evaluator. Der allgemeine Marktscanner bleibt unter `/market-scanner`.

## Stärken

- Klare Trennung Scan ↔ Lösung (`reference_scan` lehnt Lösungsfelder ab; Evaluator separat).
- 27 Referenzfälle kanonisch in `data/hebeltrader/teaser-cases.json`; historische 10/7/1 nur für 1–18.
- Offline-Hypothesen aus `structure_screen` + neues `market_screen` (Chart-Hinweise).
- Point-in-time / Leakage-Schranken dokumentiert und getestet.
- Suite: **498 passed, 6 skipped** (`tests/hebeltrader`).

## Schwächen (priorisiert)

1. **Evidenz-Scanner: 0 Identifikationen** ohne Quellenpakete und ohne `publication_at`.
2. **Universum:** 115 Namen, nur **34 mit Ticker** → Marktdaten-Screen deckt kaum ab.
3. **Offline-Hypothesen:** 6/25 Treffer nur als Entwicklungsdiagnostik; viele klare Namen ohne Vorschlag.
4. **Kein eingefrorener Blindtest** für 202/26 („Comeback-Story“), obwohl im Arbeitsprotokoll verlangt.
5. **Keine EODHD-Snapshots** im Repo; Token hier nicht gesetzt → Chart-Ranking nicht kalibriert.
6. Doppelte Welten (V3-Fixture/Detective vs. Primary Investigate) erhöhen Wartungslast.

## Fortschritt in diesem Branch (nach Review)

A–D oben erledigt (Ticker 115/115, Blind-Freeze, `--snapshots`, Doku). Live-Export:
**106/115** Snapshots. Acht Japan-`.TSE`-Primärlistings bleiben **bewusst** ohne Kursfeatures
(EODHD ohne Japan-Venue; Teaser treffen Japan selten — kein ADR-/Xetra-Fallback; siehe
`global_universe.json` → `accepted_snapshot_gaps`). Ansys: unzureichende Historie.

Abnahmeziel „sehr hohe Top-3-Wahrscheinlichkeit“ bleibt **unbelegt**, bis prospektive Blindtests
mit späteren Auflösungen existieren.
