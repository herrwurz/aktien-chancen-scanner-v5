# Scanner V6 V2.0: IV-Pfade und Verlustzerlegung

V2.0 ergänzt V1.9 um eine opt-in Forschungsanalyse. Historische JNJ- und EZB-Daten bleiben reale,
SHA-gebundene Modelleingaben. Sämtliche HS5RMP-Preise, Geldkurse, Ausführungen, IV-Verläufe und
Renditen bleiben hypothetische Black-Scholes-Merton-Ergebnisse. Der Bericht setzt
`observed_hs5rmp_quotes_used=false`.

## Drei isolierte IV-Verläufe

Jedes konservative, mittlere und optimistische Marktszenario wird mit denselben Aktienkursen,
FX-Fixings, Zinsen, Dividendenannahmen, Spreads und Handelsregeln dreimal gerechnet:

- `constant_entry_iv`: Die am Einstieg aus dem jeweiligen RV-Fenster und IV-Multiplikator
  abgeleitete IV bleibt konstant.
- `rolling_realized_volatility`: Der V1.9-Pfad verwendet täglich die bis zur Sitzung bekannte
  rollierende RV und den unveränderten hypothetischen Multiplikator.
- `explicit_iv_stress`: Die Einstiegs-IV wird mit einem ausdrücklich hypothetischen, linear von
  Faktor 1,0 auf 0,5 fallenden Stresspfad multipliziert.

Der Stresspfad ist weder beobachtete HS5RMP-IV noch eine Anpassung an den Empfehlungspreis. Die
Konfiguration enthält Status, Zeitraum, Faktoren und Begründung. Dadurch lässt sich insbesondere
untersuchen, ob ein Rückgang wie 30,82 % auf 15,55 % den starken optimistischen Modellverlust
verursacht, ohne andere Eingaben zu verändern.

## Preisänderungszerlegung

Für jeden Pfad und Bewertungstag wird die BSM-Fair-Value-Änderung gegenüber dem Einstieg in EUR
zerlegt. Aktienkurs, Zeit, IV und FX werden jeweils einzeln vom Einstiegszustand auf den aktuellen
Wert gesetzt. `interaction` ist der exakte Restbetrag aus Nichtlinearität und Reihenfolgeeffekten.
Die fünf Werte summieren sich dadurch wieder exakt zur gesamten modellierten Fair-Value-Änderung.
Spread und Ausführungsslippage gehören bewusst nicht zur Fair-Value-Zerlegung; sie erscheinen in
den Ausführungspfaden. Bei einem einzelnen abgeschlossenen Exit ergänzt `execution_attribution`
eine exakte Brücke vom Fair Value zum modellierten Ergebnis: Einstiegsspread, Ausstiegsspread und
zusätzliche Slippage werden zu Aktien-, Zeit-, IV-, FX- und Interaktionskomponenten addiert. Die
Summe entspricht dem hypothetischen P&L je Optionsschein. Mehrteilige oder noch offene Pfade werden
hier nicht scheinpräzise zusammengefasst, sondern als nicht verfügbar gekennzeichnet.

## Slippage und 20-Tage-Regel

Jeder IV-Pfad wird mit drei zusätzlichen Exit-Abschlägen gerechnet:

- `zero`: 0 %,
- `baseline`: die bisherige Szenarioannahme,
- `stress`: 25 % als explizite Illiquiditäts-Stressgrenze.

Der Stresswert ist kein beobachteter HSBC-Spread. Jeder Exit nennt Geldkurs vor Slippage,
Slippage-Satz und Geldkurs nach Slippage getrennt.

Die V1.9-Strategie erzeugt das Verlustsignal am Schluss und handelt am modellierten Geldkurs der
nächsten Sitzungseröffnung. `hold_after_loss_signal` ist eine eigene Forschungsstrategie: Sie
protokolliert dasselbe Signal, ignoriert nur diesen Exit und lässt die übrigen Ziel-/Stoppregeln
weiterlaufen. Ihre Ergebnisse dürfen nicht mit der empfohlenen Strategie vermischt werden.

Die Referenz 0,17 EUR wird je Szenario und IV-Pfad separat mit dem modellierten Einstieg verglichen.
`calibration_performed=false` verhindert eine Interpretation als automatische Parameteranpassung.

## Offline-Lauf auf Hetzner

Der Befehl benötigt keine neue Datenbeschaffung, kein Netzwerk und keinen API-Key. Er startet keine
Compose-Dienste und bindet alle privaten Archive schreibgeschützt ein.

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
ASSUMPTIONS="$PWD/docs/hebeltrader-hs5rmp-model-assumptions-v20.example.json"
OUTPUT_NAME="hs5rmp-iv-attribution-v20-$(date -u +%Y%m%dT%H%M%SZ).json"

docker run --rm --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$CURRENT,dst=/input/current.json,readonly" \
  --mount "type=bind,src=$PRIOR,dst=/input/prehistory.json,readonly" \
  --mount "type=bind,src=$FX,dst=/input/fx.csv,readonly" \
  --mount "type=bind,src=$AUDIT,dst=/input/audit.json,readonly" \
  --mount "type=bind,src=$ASSUMPTIONS,dst=/input/assumptions.json,readonly" \
  --mount "type=bind,src=$ROOT,dst=/reports" \
  chancen-scanner-v6:local \
  python -m scanner.hebeltrader.derivatives_cli scenario-v20 \
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
r=json.load(open(sys.argv[1], encoding="utf-8"))
assert r["observed_hs5rmp_quotes_used"] is False
print("Bericht:", sys.argv[1])
print("Referenz 0,17 EUR:", r["indicative_entry_reference"])
for scenario, analysis in r["scenario_analysis"].items():
    print("\n", scenario)
    for iv_path, item in analysis["iv_paths"].items():
        base=item["baseline_slippage"]
        print(iv_path, "entry=", base["entry_ask"], "exit=", base["exit_value"],
              "return_pct=", base["return_pct"], "events=", base["events"])
        print("slippage=", {k:v["return_pct"] for k,v in item["slippage_paths"].items()})
        print("hold=", item["hold_after_loss_signal"])
        print("final_attribution=", item["attribution"][-1] if item["attribution"] else None)
        print("execution_attribution=", item["execution_attribution"])
PY
```

Die echte Serverausgabe ist erforderlich, um die gemeldeten Verluste und die reale JNJ-Datenreihe
zu reproduzieren. In der Entwicklungsumgebung werden ausschließlich synthetische Offline-Fixtures
verwendet; daraus werden keine Aussagen über tatsächlich erzielte HS5RMP-Renditen abgeleitet.
