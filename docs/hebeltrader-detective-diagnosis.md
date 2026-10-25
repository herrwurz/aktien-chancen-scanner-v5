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

## Beispiel: drei reale Werbe-Teaser (ohne Gold-Label)

Publikationszeit hier nur Platzhalter (`2025-10-01+02:00`). Nach Lexikon-Nachzug:

| Fall | Extrahiert | Outcome | Bedeutung |
|---|---|---|---|
| Gesundheitssektor + Wall-Street, +1761 % | `healthcare`, `US`, Umsatz/Ertrag | `all_candidates_contradicted` | EU-Seed hat Pharma, aber **US**-Hinweis widerspricht DE/CH-Namen → korrekt keine Fake-Aktie |
| Finanzschwergewicht, +1705 % | `finance`, Ertrag | `retrieval_missed` | Sektor erkannt, **kein Finanzwert** im kuratierten Universum |
| Handels-Gigant, +1438 % | `retail` | `retrieval_missed` | Sektor erkannt, **kein Retail-Titel** im Seed |

Vor dem Lexikon-Nachzug war bei allen dreien nur die Promo-Prozentzahl sichtbar
(`insufficiently_constrained`) — der Detektiv wirkte „blind“, obwohl der Text Sektor/Region nennt.

## Was als Nächstes braucht echte Teaser

1. Dieselben Teaser mit **belegter** `publication_at` + erlaubtem `rights_status` und optional Gold-WKN
2. Universum/News für US-Healthcare, Finance und Retail (lizenziert, point-in-time)
3. Diagnose-CSV über 5–10 weitere Originalteaser
4. UI: bei `hypothesis_top3` klar „Hypothesen“; bei `unresolved` den `failure_code` zeigen

Ohne Schritt 2 bleibt die Identifikation dieser drei Themen blockiert — absichtlich, statt falsche EU-Namen.
