# Weg zum Ticker-Ergebnis

Stand: 2026-10-30.

## In einem Satz

**Teaser mit harten Ankern + datiertes IR/SEC-Paket → `packet_evidence.ticker`;
Live-Falsifikation → formales `identified`.**

## Stufen

| Stufe | Feld | Bedeutung |
|---|---|---|
| 0 Chart/Sektor | `market_hypotheses` | unverifizierte Vorschläge |
| 1 Teil-Evidenz | `packet_evidence=partial_evidence` | 1 Kernhinweis (z.B. Emittentenname) |
| 2 Ticker-Hypothese | `packet_evidence=ticker_hypothesis_ready` | ≥2 Kernhinweise, klarer Vorsprung |
| 3 Identifiziert | `identification=identified` | plus Live-Falsifikation & ≥5 Gegenkandidaten |

Offline-Scans stoppen bewusst bei Stufe 2 (`identification` bleibt `not_identified`).

## Was der 27er-Korpus hergibt

- Anonyme Teaser → Stufe 0–1 ohne Anreicherung
- HT-023 (AbbVie im Headline) → Stufe 1 (`partial_evidence`, ABBV)
- HT-027 mit Clario+Solventum (Diagnose-Anreicherung) → Stufe 2 (`ticker_hypothesis_ready`, TMO)

## Operator-Pfad für den nächsten echten Call

1. Teaser + `publication_at` sichern (vor Call-PDF).
2. ≥2 Anker im Teaser (Eigenamen mit Relation und/oder Kennzahl).
3. IR/SEC-Paket vor Cutoff mit Binding.
4. Offline-Scan: Ziel `packet_evidence.status=ticker_hypothesis_ready`.
5. Live-Lauf: Falsifikation → `identified`.

Blind 202/26 und Chart-Scores bleiben unangetastet.
