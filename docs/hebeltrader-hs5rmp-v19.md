# Scanner V6 V1.9: historische Modellinputs für HS5RMP

V1.9 ersetzt im Modellmodus den konstanten USD/EUR-Wert und die feste Volatilität durch
punktgenaue Offline-Eingaben. Die privaten Dateien verbleiben auf Hetzner und werden nur über
SHA-256 an den Ergebnisbericht gebunden. Es findet kein Netzwerkzugriff statt.

## Methodik und Grenzen

Für jede JNJ-Handelssitzung werden 20, 60 und 120 adjustierte Schlusskursrenditen verwendet. Die
Berechnung nutzt logarithmische Renditen, die Stichproben-Standardabweichung und `sqrt(252)`.
Jeder Wert endet am vorherigen Handelstag. Damit ist der Schlusskurs der gerade bewerteten
Tageskerze nicht enthalten.

Der FX-Wert ist das letzte EZB-Fixing **vor** der bewerteten Sitzung. Das verhindert, dass eine
Simulation am US-Markttagesbeginn ein erst später veröffentlichtes gleich­tägiges Fixing kennt.
Wochenenden und EZB-freie Börsentage werden durch Rückgriff auf das letzte frühere Fixing mit
Fixingdatum und Alter ausgewiesen. Ein EZB-Referenzkurs ist kein ausführbarer Intraday-Kurs.

Die realisierte Volatilität ist ebenfalls kein beobachteter Optionsscheinparameter. Jedes Szenario
wendet einen ausdrücklich hypothetischen IV-Multiplikator auf ein ausgewiesenes Fenster an:

| Szenario | RV-Fenster | hypothetischer IV-Multiplikator |
|---|---:|---:|
| konservativ | 120 Sitzungen | 0,85 |
| mittel | 60 Sitzungen | 1,00 |
| optimistisch | 20 Sitzungen | 1,15 |

Bezugsverhältnis 0,1 und europäische Ausübung bleiben unbestätigt. BSM-Modellpreise werden daher
nie nach `OBSERVED_DERIVATIVE` übernommen. Die Abweichung zu 0,17 EUR vergleicht ein hypothetisches
Modellergebnis mit einem indikativen Empfehlungspreis und belegt keine damalige Ausführbarkeit.

Die Datenqualitätsausgabe enthält Dateihashes, Sitzungs- und Fixingzahlen, mehr als vier
Kalendertage lange Preislücken, Corporate Actions, fehlende Volatilitätsfenster und getragene
FX-Fixings. Splits blockieren wie in V1.8 das Derivatemodell bis zur Produktanpassungsprüfung.

## Vollständig offline auf Hetzner ausführen

Der Block setzt einen Merge des PR voraus, führt selbst aber weder Merge noch Deployment aus. Er
startet keine Compose-Dienste, greift nicht auf PostgreSQL oder Immich zu und benötigt keinen
API-Key. Die vier privaten Quelldateien werden schreibgeschützt eingebunden.

```bash
set -euo pipefail
cd /opt/aktien-chancen-scanner-v5
git switch main
git pull --ff-only origin main
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD muss bereits gesetzt sein}"
docker compose build api

ROOT="$PWD/reports/hebeltrader"
CURRENT="$ROOT/tiingo-pilot-jnj/jnj-normalized-v17.json"
PRIOR="$ROOT/market-inputs-v18/jnj-prehistory-2025.json"
FX="$ROOT/market-inputs-v18/ecb-usdeur-2025-2026.csv"
AUDIT="$ROOT/market-inputs-v18/jnj-model-input-audit.json"
ASSUMPTIONS="$PWD/docs/hebeltrader-hs5rmp-model-assumptions-v19.example.json"
OUTPUT_NAME="hs5rmp-historical-inputs-v19-$(date -u +%Y%m%dT%H%M%SZ).json"

docker run --rm --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$CURRENT,dst=/input/current.json,readonly" \
  --mount "type=bind,src=$PRIOR,dst=/input/prehistory.json,readonly" \
  --mount "type=bind,src=$FX,dst=/input/fx.csv,readonly" \
  --mount "type=bind,src=$AUDIT,dst=/input/audit.json,readonly" \
  --mount "type=bind,src=$ASSUMPTIONS,dst=/input/assumptions.json,readonly" \
  --mount "type=bind,src=$ROOT,dst=/reports" \
  chancen-scanner-v6:local \
  python -m scanner.hebeltrader.derivatives_cli scenario \
    --underlying /input/current.json \
    --prehistory /input/prehistory.json \
    --fx /input/fx.csv \
    --input-audit /input/audit.json \
    --expected-underlying-manifest-sha256 0b48d417a5f896740dd138d5621fbb369ba09762c04f84adc7c001195998f075 \
    --expected-current-sessions 115 \
    --expected-prehistory-prices 146 \
    --expected-fx-fixings 266 \
    --expected-dividends 2 \
    --expected-splits 0 \
    --assumptions /input/assumptions.json \
    --publication-at 2025-08-05T08:15:00+02:00 \
    --output "/reports/$OUTPUT_NAME"

python3 - "$ROOT/$OUTPUT_NAME" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
q = r["historical_market_input_quality"]
assert q["current_session_count"] == 115, q
assert q["prehistory_price_count"] == 146, q
assert q["fx_fixing_count"] == 266, q
assert q["split_event_count"] == 0, q
assert q["dividend_event_count"] == 2, q
print("Datenqualität:", q)
for mode, value in r["modes"].items():
    print("\n", mode, value["status"])
    for name, scenario in value.get("scenarios", {}).items():
        first = scenario.get("path", [{}])[0].get("market_inputs")
        print(name, "entry=", scenario.get("entry_ask"), "exit=", scenario.get("exit_value"),
              "return_pct=", scenario.get("return_pct"), "events=", scenario.get("events"),
              "entry_inputs=", first)
print("Vergleich 0,17 EUR:", r["modes"]["MODELED_DERIVATIVE"].get("indicative_entry_comparison"))
print("Sensitivität:", r["modes"]["MODELED_DERIVATIVE"].get("entry_price_sensitivity"))
print("Bericht:", sys.argv[1])
PY
```

Die bereits gemeldeten Werte von 26,698 %, 20,906 % und 23,173 % werden erst durch die echte
Serverausgabe bestätigt. Codex hatte keinen Zugriff auf die vier Dateien und behauptet deshalb
keinen realen Pilot-Return.

## Ausführungszeitpunkt und Slippage

Die bedingte 20-Tage-Verlustregel erzeugt im historischen V1.9-Pfad am Tagesschluss zunächst nur
ein `conditional_loss_signal`. Ausgeführt wird vor der Auswertung von Hoch und Tief der nächsten
vorhandenen Handelssitzung zu deren modelliertem Geldkurs bei Eröffnung. Der Ergebnisbericht nennt
Signal- und Ausführungsdatum, `modeled_bid_before_slippage`, `additional_slippage_pct` und
`execution_bid_after_slippage` getrennt. Dadurch kann ein Schlusskurssignal vom 18.09.2025 nicht
rückwirkend am selben Schlusskurs handeln.

Die Hetzner-Kontrollwerte bleiben Regressionsevidenz für die Ausführungslogik: konservativ
−23,00 % am bisherigen Schluss gegenüber −3,40 % an der nächsten Eröffnung, mittel −18,46 %
gegenüber −7,95 %. Sie werden nicht als beobachtete HS5RMP-Quotes interpretiert. Der reale
19.09.2025-JNJ-Eröffnungskurs von 174,69 USD ist ein Basiswertinput; der daraus modellierte
Optionsschein-Geldkurs und jede Slippage bleiben hypothetisch.

Stopps, Ziele und signalbasierte Ausstiege verwenden dieselben Ausführungsfelder. Zielausführungen
haben im Modell keine zusätzliche Slippage, Stopps und signalbasierte Ausstiege verwenden den
jeweiligen `gap_haircut_pct` als offen ausgewiesene zusätzliche Slippage. Der V1.8-Pfad ohne
historische Marktinputschicht behält zur Vergleichbarkeit seine Ausführung am gleichen
modellierten Schluss-Geldkurs und kennzeichnet sie mit
`same_session_modeled_bid_close_v18_compatibility`.

## Readiness für 118 Empfehlungen

`readiness` prüft nur, ob vier Marktinput-Typen deklariert und Produktbedingungen verifiziert
sind. Es führt ausdrücklich kein Modell aus:

```bash
python -m scanner.hebeltrader.derivatives_cli readiness \
  --manifest /secure/hebeltrader-v19-readiness.json \
  --output reports/hebeltrader/v19-readiness.json
```

Unbestätigte Produktbedingungen ergeben `blocked_unverified_product_terms`; `modeled_count` bleibt
`0`. Eine Batchbewertung aller 118 Empfehlungen ist damit vorbereitet, aber
nicht freigegeben.
