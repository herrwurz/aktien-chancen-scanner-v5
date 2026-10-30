# Original-Teaser: Named-Anchor-Lücke

Stand: 2026-10-30.

## Kurzfassung

Im Entwicklungs-Korpus (27 Refs) gibt es **keinen** Original-Teaser mit ≥2
bestätigbaren spezifischen Ankern für den Evidenzkanal. Tooling (SEC-Binding,
Issuer-Anaphora, Gewinnsprung-Extraktion) ist nicht der Engpass — **Teaser-
Anonymität** ist es.

Details und HT-023-Baseline:
`docs/examples/source-packets/pilot-original-anchors/`.

## Abgrenzung

| Signal | Status |
|---|---|
| Chart/Sektor (Pool-PIT) | reicht nicht allein (`B_chart_rank`) |
| Entwicklungs-Anreicherung (Clario/Solventum) | beweist Matcher, nicht Korpus |
| Call-PDF-Produkte/Übernahmen | Resolutionsleak — verboten als Paket |
| Original-Teaser ≥2 Named-Facts | **0/27** |

## Operator-Checkliste für den nächsten echten Fall

1. Teaser sichern **bevor** Call-PDF gelesen wird.
2. `publication_at` notieren.
3. Mindestens zwei spezfische Anker im Teaser (Eigenamen mit Relation und/oder
   Kennzahl mit Bezug).
4. IR/SEC-Paket vor Cutoff mit Binding.
5. Offline-Scan einfrieren, erst dann Auflösung.
