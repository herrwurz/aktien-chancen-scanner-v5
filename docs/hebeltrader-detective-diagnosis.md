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

## Was als Nächstes braucht echte Teaser

1. 5–10 unveränderte Originalteaser + belegte `publication_at` + erlaubter `rights_status`
2. Diagnose-Lauf je Fall (CSV) und Häufigkeitszählung der `failure_code`s
3. Eine lizenzierte, zeitpunktgenaue EU/DACH-Nachrichten-/Identitätsquelle (0–20 EUR/Monat)
4. UI: bei `hypothesis_top3` klar „Hypothesen, manuell prüfen“; bei Gleichstand keinen
   Einzelgewinner als WKN hervorheben

Ohne Schritt 1–3 bleibt die reale Erkennungsrate ungemessen; Code-Rewrites ersetzen das nicht.
