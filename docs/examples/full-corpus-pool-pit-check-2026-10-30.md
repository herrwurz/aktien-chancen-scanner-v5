# Vollständige Korpus-Prüfung (Pool-PIT + Dedup), 2026-10-30

## Was geprüft werden konnte

| Prüfung | Status |
|---|---|
| 27er Offline-Struktur Top-8 | ja |
| 27er Market Chart Pool-PIT Top-8 (Dedup) | ja |
| Blind 202/26 Market Pool-PIT | ja |
| Treffer vs Lösungen (Entwicklungsdiagnostik) | ja |
| Evidenz-Identifikation mit Publisher-PDFs | **nein** — PDFs nicht im Repo |
| Historische Quellenpakete | **nein** — `publication_at` = **0/27** |

Snapshots: Remap-Pool-PIT (`coverage` 979–981). Universum nach Ticker-Dedup (~1044 Symbole).

## Market (Chart)

| Lauf | graded | Top1 | Top3 | Top8 |
|---|---:|---:|---:|---:|
| Pool-PIT vor Dedup | 25 | 2 | 3 | 7 |
| **Pool-PIT + Dedup** | 25 | 2 | 3 | 7 |

Hits: HT-003 Costco #1, HT-001 ADI #1, HT-023 AbbVie #2, HT-014 SAP #4,
HT-002 Zurich #5, HT-005 MU #5, HT-020 SNPS #6.

## Offline (Sektor)

| graded | Top1 | Top3 | Top8 | suggestion_cases |
|---:|---:|---:|---:|---:|
| 25 | 2 | 4 | 6 | 17 |

## Blind 202/26

| Kennzahl | Wert |
|---|---|
| DBK im Universum/PIT | ja |
| In Top-8 | **nein** |
| Score / Rang | 10 / **565** (vorher ~622) |
| Score-23-Namen | 98 (vorher 112) |
| Top-8 | APA, A, AI.PA, APD, ALLFG.AS, MO, AMGN, AAPL (kein Duplikat mehr) |

Freeze unverändert. Residual weiter **B_chart_rank**. Kein Score-Retuning.

## Lücken in den Falldaten

- Ohne Teasertext: HT-016, HT-022, HT-023, HT-025 (Market teils trotzdem via Headline/Datum).
- Ohne Lösung: HT-016, HT-019.
- Kein Fall mit `publication_at` → Evidenz-Scanner bleibt bei 0 Identifikationen.

## Nächster echter Hebel

Publisher-Reports lokal halten (nicht committen) + `publication_at` + Quellenpakete.
Chart allein reicht für den Korpus nicht.

JSON: `full-corpus-pool-pit-check-2026-10-30.json`.
