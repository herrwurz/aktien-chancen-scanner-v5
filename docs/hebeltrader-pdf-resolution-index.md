# Publisher-PDF Resolutionsindex

Stand: 2026-10-30.

## Policy

Die hochgeladenen HEBELTRADER-PDFs sind **Auflösungs-/Ground-Truth-Artefakte**.
Sie dürfen **nicht** als Identifikations-Quellenpakete in den Investigator
(mit `company_name` = Lösung) eingespeist werden — das wäre ein Leak.

| Nutzung | Erlaubt |
|---|---|
| Call-WKN, Issue, `publication_at`-Guess, Headline | ja (Inventar/Index) |
| Scan-Inputs `publication_at` füllen | ja (Guess kennzeichnen) |
| Chart-/Sektor-Diagnose PIT | ja |
| PDF als Evidence-Dokument mit Lösungsnamen | **nein** |
| Echte Quellenpakete = IR/SEC/Ad-hoc vor Cutoff | später, separat |

JSON: [`hebeltrader-pdf-resolution-index.json`](hebeltrader-pdf-resolution-index.json).

## Scan-Inputs mit Uhrzeit-Guess

- `docs/examples/reference-27-inputs-with-publication-at.json` — 24/27 Fälle
- `docs/examples/blind-202-26-inputs-with-publication-at.json`

Basis: PDF-Zeile `Stand: TT.MM.JJJJ um HH:MM Uhr` (typisch 08:15). Kein Beweis einer
Börsenuhr; für historische Blind-Pakete weiterhin Operator-Bestätigung nötig.

## Lücken

- HT-016 — kein PDF / keine Issue im Archiv (HT-003 Costco **192/26** und
  HT-012 BASF **137/26** seit 2026-10-31 im lokalen Archiv; Stand → shared refs)
  (Costco **70/26** liegt separat vor, ist ein anderer Call).
