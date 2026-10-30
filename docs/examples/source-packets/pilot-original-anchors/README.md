# Original-Teaser-Anker (Korpus-Lücke)

Entwicklungsdiagnose — kein Blind-Benchmark. Frage: Gibt es im 27er-Korpus
**Original-Teaser** (ohne Call-PDF, ohne Anreicherung) mit ≥2 bestätigbaren
spezifischen Ankern?

## Antwort

**Nein.** `corpus-gap.json`:

| Metrik | 27er |
|---|---|
| `publication_at` vorhanden | 24 |
| ≥1 Named-Relation (`acquisition\|…` o.ä.) | **0** |
| ≥1 `financial_metric` (z.B. Gewinnsprung) | 3 |
| ≥1 Entity im Teaser | 1 (HT-023 AbbVie) |
| ≥2 spezifische Anker | **0** |

Produktseitig sind Teaser anonym. Der Clario/Solventum-Pfad (#64/#65) war
**Entwicklungsanreicherung**, kein Original-Signal.

## HT-023 Baseline (einziger Eigenamen)

Headline nennt den Emittenten: `AbbVie: …`. Paket: AbbVie 10-Q/8-K + Pharma-Peers.

| Ergebnis | Wert |
|---|---|
| `source_packet_status` | provided |
| checked | 7 |
| bestätigte Kernhinweise | 0 |
| Entscheidung | `ambiguous_tie` |

Ursache: `unknown_relation|abbvie` ist kein bestätigbares `fact_claims`-Relation-
Muster (`acquisition`/`investment`/`partnership`). Emittentenname allein reicht
für das 2-Hinweis-Gate nicht.

Call-PDF enthält Skyrizi/Rinvoq/Humira — **Resolutionsleak**, nicht als Teaser-
oder Paket-Input verwenden.

## Dateien

| Datei | Rolle |
|---|---|
| `corpus-gap.json` | Zählung aller 27 Original-Teaser |
| `HT-023.*` | Named-Issuer-Baseline-Scan |

## Nächster Schritt (operatorisch)

1. Neue/prospective Teaser mit ≥2 Eigenamen oder Kennzahlen **im Teasertext**.
2. Oder bewusst Product-Entscheidung: Emittentenname-im-Teaser als Identity-Kanal
   (separat vom Fact-Claim-Gate) — kein Score-Retuning der Chart-Schicht.
3. Blind 202/26 unverändert.
