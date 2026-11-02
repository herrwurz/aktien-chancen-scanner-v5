# Original-Teaser: Named-Anchor-Lücke

Stand: 2026-10-31.

## Kurzfassung

Im Entwicklungs-Korpus (corpus-v1, 26 aktive Refs; HT-016 dropped) gibt es **keinen**
Original-Teaser mit ≥2 bestätigbaren spezifischen Ankern für den Evidenzkanal
(`originals identified: 0/26`; 25× `insufficient_evidence`, HT-023
`partial_evidence` via `issuer_literal`). Tooling (SEC-Binding, Issuer-Anaphora,
Gewinnsprung-Extraktion) ist nicht der Engpass — **Teaser-Anonymität** ist es.

Scorecard: `python3 -m scanner.hebeltrader.detective.corpus_report originals`.
pad800 market Top-8 trifft nur 2/3/7 Original-Lösungen und bestätigt nur 7/26
named packet leaders — Chart ersetzt keine Named-Anker.

Wenn der Teaser den Emittenten **wörtlich** nennt (HT-023 AbbVie), bindet der
`issuer_literal`-Kanal den Namen an das passende Paket → Top-1 / 
`plausible_hypothesis` (weiterhin 1/2 Kernhinweise, Offline nicht `identified`).

Details: `docs/examples/source-packets/pilot-original-anchors/`.

## Abgrenzung

| Signal | Status |
|---|---|
| Chart/Sektor (Pool-PIT) | reicht nicht allein (`B_chart_rank`) |
| Entwicklungs-Anreicherung (Clario/Solventum) | beweist Matcher, nicht Korpus |
| Call-PDF-Produkte/Übernahmen | Resolutionsleak — verboten als Paket |
| Original-Teaser ≥2 Named-Facts | **0/27** |
| Emittentenname im Teaser (`issuer_literal`) | HT-023: ABBV Top-1, Score 54 |

## Operator-Checkliste für den nächsten echten Fall

1. Teaser sichern **bevor** Call-PDF gelesen wird.
2. `publication_at` notieren.
3. Mindestens zwei spezfische Anker im Teaser (Eigenamen mit Relation und/oder
   Kennzahl mit Bezug).
4. IR/SEC-Paket vor Cutoff mit Binding.
5. Offline-Scan einfrieren, erst dann Auflösung.
