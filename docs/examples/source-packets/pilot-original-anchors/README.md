# Original-Teaser-Anker (Korpus-Lücke + Issuer-Literal)

Entwicklungsdiagnose — kein Blind-Benchmark.

## Korpus

`corpus-gap.json`: **0/27** Original-Teaser mit ≥2 nativen spezifischen Ankern
(Named-Relation oder Finanzkennzahl). Produktseitig anonym.

| Metrik | 27er |
|---|---|
| ≥1 Named-Relation (`acquisition\|…`) | 0 |
| ≥1 `financial_metric` | 3 |
| ≥1 Entity | 1 (HT-023 AbbVie) |
| ≥2 spezifische Anker | **0** |

## Identity-Kanal: `issuer_literal`

Bare Eigenamen ohne Transaktionskontext werden als `issuer_literal|<name>`
extrahiert und nur bestätigt, wenn `canonical_company(packet)` dem Namen
entspricht (kein Filing-Body-Subject nötig).

Das ist **kein** Chart-Score-Retuning und kein Call-PDF-Leak.

## HT-023 Baseline (nach Issuer-Literal)

Headline: `AbbVie: …`. Paket: AbbVie 10-Q/8-K + Pharma-Peers.

| Ergebnis | Wert |
|---|---|
| `source_packet_status` | provided |
| checked | 7 |
| Top-1 | **ABBV** (Score 54, Quote `AbbVie`) |
| `packet_evidence` | `partial_evidence` → ABBV |
| Entscheidung | `plausible_hypothesis` |
| `identified` | nein (1/2 Kernhinweise + Offline-Gates) |

Vorher (ohne Issuer-Literal): Score 0 / `ambiguous_tie`.

Call-PDF-Produkte (Skyrizi/Rinvoq) bleiben Resolutionsleak.

## Dateien

| Datei | Rolle |
|---|---|
| `corpus-gap.json` | Zählung aller 27 Original-Teaser |
| `HT-023.*` | Named-Issuer-Baseline-Scan |

## Nächster Schritt

Prospective Teaser mit zweitem Anker **oder** Live-Falsifikation — Blind 202/26
unverändert.
