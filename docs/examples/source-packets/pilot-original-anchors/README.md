# Original-Teaser-Anker (Korpus-Lücke + Issuer-Literal)

Entwicklungsdiagnose — kein Blind-Benchmark.

## Korpus

`corpus-gap.json`: **0/27** Original-Teaser mit ≥2 nativen spezifischen Ankern
(Named-Relation oder Finanzkennzahl). Produktseitig anonym.

Refresh:

```bash
python3 scripts/refresh_original_anchor_gap.py
```

| Metrik | 27er (refresh 2026-10-31) |
|---|---|
| ≥1 Named-Relation (`acquisition\|…`) | 0 |
| ≥1 `financial_metric` | 3 |
| ≥1 Entity | 3 (incl. HT-023 AbbVie; HT-016 full teaser) |
| ≥2 spezifische Anker | **0** |

## Identity-Kanal: `issuer_literal`

Bare Eigenamen ohne Transaktionskontext werden als `issuer_literal|<name>`
extrahiert und nur bestätigt, wenn `canonical_company(packet)` dem Namen
entspricht (kein Filing-Body-Subject nötig).

Das ist **kein** Chart-Score-Retuning und kein Call-PDF-Leak.

## HT-023 (Issuer + Produkte)

Paket: AbbVie 10-Q/8-K (Skyrizi/Rinvoq-Prosa) + Pharma-Peers.

| Inputs | `packet_evidence` | `identification` |
|---|---|---|
| original (Headline AbbVie) | partial → ABBV (1 Hinweis) | not_identified |
| named (+ Wachstumstreiber Skyrizi/Rinvoq) | ready → ABBV (3 Hinweise, Score 156) | **identified** (`historical_source_packet`) |

Call-PDF bleibt Resolutionsleak; named ist Diagnose-Anreicherung.

## Dateien

| Datei | Rolle |
|---|---|
| `corpus-gap.json` | Zählung aller 27 Original-Teaser |
| `HT-023.*` | Named-Issuer-Baseline-Scan |

## Status

HT-023 named schließt den Offline-Identitätskanal (Stufe 3a) für dieses Paket.
Nächster Hebel: weitere Original-Teaser mit Produkt-/Issuer-Ankern + SEC-Paket
(`build_sec_packet`). Blind 202/26 unverändert. Batch:
`../evidence-batch-pilots-2026-10-30.json`.
