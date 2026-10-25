# Detektiv: Teaser-Diagnose und nächste Schritte

Der Detektiv-Code bleibt. Falsche Top-Treffer kommen vor allem aus dünnen Hinweisen,
Gleichständen und fehlender realer Abdeckung — nicht aus einer grundsätzlich falschen Pipeline.

## Diagnose-CLI

Pro Fall: Status, `failure_code`, extrahierte Hinweise, Top-3 mit Gründen, optional Label-Outcome.

```bash
python -m scanner.hebeltrader.detective.diagnose \
  --inputs tests/fixtures/detective-hypothesis/mini_benchmark/manifest.json \
  --labels tests/fixtures/detective-hypothesis/mini_benchmark/labels.json \
  --output-prefix /tmp/detective-diagnosis/mini \
  --service hypothesis_fixture
```

Ausgaben: `.json`, `.md`, `.csv`. Das ist **keine** kalibrierte Trefferquote.

Für eigene Teaser ein Manifest analog zu
`tests/fixtures/detective-hypothesis/mini_benchmark/manifest.json` außerhalb von Git legen
(Rechte + Publikationszeit mit Offset). Gold-Labels erst nach dem Scan zuführen.

## Befund am Mini-Korpus (vor Geo-Fix)

| Muster | Beispiel | Wirkung |
|---|---|---|
| Länderadjektiv fehlt | „Deutscher Logistik-Gigant“ ohne `countries:DE` | Schweizer Name oft Platz 1 bei Punktegleichstand |
| Gleichstand | mehrere Kandidaten score=32 | `selected_asset_id` = erster der Liste wirkt wie sicherer Treffer |
| Promo/generisch | nur „1.717 %“ / Buyback ohne Sector | korrekt `unresolved` / `insufficiently_constrained` |
| Hypothesen-UI | Status `hypothesis_top3` | manuell prüfen, keine automatische Bestätigung |

## Sofortmaßnahme im Code

Länderlexikon erkennt jetzt u. a. `deutscher` / `deutsche` / `deutschland` und
`amerikanischer` / `US-Pharmakonzern`. Damit widerspricht ein CH-Kandidat einem `DE`-Hinweis
hart und rutscht hinter deutsche Logistiknamen. Nach dem Fix ist
`german-logistics-heavyweight` Top-1 `isin:DE0005552004` (DHL), nicht mehr Kuehne + Nagel.

## Beispiel: drei reale Werbe-Teaser

Publikationszeit hier nur Platzhalter (`2025-10-01+02:00`). Gold-Call-WKNs (OpenFIGI-Namen der
Scheine, nicht als offizielle Produktbestätigung im Detektiv):

| Teaser | Gold-Call | Underlying | Extrahiert | Nach US-Seed |
|---|---|---|---|---|
| Gesundheit + Wall-Street, +1761 % | `JE11C1` | J&J (`cik:0000200406`) | `healthcare`, `US` | Top-3 enthält JNJ (mit PFE/UNH) |
| Finanzschwergewicht, +1705 % | `MN6CYX` | JPM (`cik:0000019617`) | `finance` | Top-3: JPM, BAC, GS |
| Handels-Gigant, +1438 % | `JY5SQZ` | COST (`cik:0000909832`) | `retail` | Top-3 enthält COST (mit TGT/WMT) |

Status jeweils `hypothesis_top3` (manuell prüfen, keine Auto-Bestätigung, **kein** einzelner
`selected_wkn`-Gewinner). Nach exaktem Sektor-Bonus steht JNJ in der Gesundheits-Top-3 vorne.
Call-WKNs stehen nicht im Teaser und werden nicht erraten; nur bei ausdrücklicher Call-WKN im Text
erscheint ein unbestätigter Derivat-Kandidat. Der US-Seed (`us_seed_universe.json`) ist kuratiert und
point-in-time über `source_available_at` gefiltert — **kein** vollständiger US-Markt.

Frühere Stufen: nur Promo-% → `insufficiently_constrained`; danach ohne US-Seed → EU-Widerspruch /
`retrieval_missed`.

## Was als Nächstes

1. Belegte `publication_at` + `rights_status` für echte Abnahme
2. US-Seed über SEC-Index/News verbreitern (weiterhin PIT, Budget 0–20 EUR)
3. UI: `hypothesis_top3` klar als Hypothese; optional Derivat erst nach expliziter WKN/Terms
4. Weitere Originalteaser in die Diagnose-CSV
