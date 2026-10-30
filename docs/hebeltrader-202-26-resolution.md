# HEBELTRADER 202/26 – prospektive Blind-Auflösung

**Miss.** Die Lösung war **Deutsche Bank** (Call **WB14HL**). Sie stand **nicht** in den
eingefrorenen Market-Top-8 und fehlte vollständig im 115er-Universum.

## Freeze (unverändert)

| Artefakt | Wert |
|---|---|
| Fall | `BLIND-202-26` |
| PIT+Exclude-Freeze | `docs/examples/blind-202-26-freeze-pit-excl/` |
| Ranking-SHA256 | `3fff83e1387325ccf8c1fc47d49940c5d9385244fd00518c1ea0c4722a331b0f` |
| Eingefrorene Top-8 | LLY, HNR1, IBE, KOG, LMT, MA, NXPI, NOVN (alle Score 23) |
| Offline | `no_local_sector_hypotheses` |
| Identifikation | `not_identified` / `insufficient_evidence` |

Keine nachträgliche Änderung an Ranking, Scores oder Filtern für diesen Fall.

## Auflösungsbeleg

Nutzer-PDF `Hebeltrader_2026-202_2822.pdf`, Ausgabe **202/2026** vom **30.10.2026**, 6 Seiten,
SHA256 `d885c19faf83bc0a7b4eab1b9c5821f9328ae1d9b5cbef0016285519595fd885`.
PDF und Volltext werden **nicht** ins Repository kopiert.

Seiten 1–4 nennen ausdrücklich Deutsche Bank, Call-WKN **WB14HL**, Aktien-WKN **514000**,
Basispreis 38,00 €, Laufzeit 19.03.2027, sowie Q3-Zahlen, Christian Sewing, Peers
(BNP / Santander / UBS / JPMorgan) und GD200-Rückeroberung.

Produktstammdaten (ISIN, Emittent, Live-Quote) wurden **nicht** unabhängig verifiziert.

## Fehlerklasse

**A – Universum.** Im kuratierten `global_universe.json` (115 Assets) gibt es keine
Deutsche Bank. Finanznamen dort: JPM, GS, Allianz, Munich Re, Hannover Rück, Berkshire.
Kein Active-Call-Ausschluss (DB war nicht in `featured_calls.json`). Kein Ranking-Fehler
innerhalb des Universums: die Aktie war schlicht nicht kandidierbar.

Begleitbefund (kein Retuning-Anlass für diesen Freeze): der Blind-Teaser war eine kurze
Clue-Zusammenfassung ohne die hochspezifischen PDF-Marker (Sewing, Peer-Banken, exakte
Gewinnzahlen). Chart/`above_gd200` allein reicht laut 27er-PIT-Diagnose nicht für Top-8.

## Maßnahmen (ohne Fall-Retuning)

1. Deutsche Bank als featured call **202/26** in die Blocklist aufnehmen (künftige Ausschlüsse).
2. Universumslücke EU-Banken als Folgeauftrag führen — Erweiterung erst nach Bestätigung,
   nicht als nachträgliche „Gewinnerregel“ für 202/26.
3. Algorithmus-Scores und Market-Ranking dieses Falls bleiben eingefroren.

Strukturierte Felder: [hebeltrader-202-26-resolution.json](hebeltrader-202-26-resolution.json).
