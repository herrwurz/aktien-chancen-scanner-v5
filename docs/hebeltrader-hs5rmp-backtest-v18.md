# Scanner V6 V1.8: HS5RMP-Backtest

Stand: 23.10.2026. V1.8 erweitert die V1.7-Pipeline für autorisierte CSV- und JSON-Exporte,
Quotegrößen, Spreads, Lücken, Stückzahlen, Gebühren und zensierte Verfallsfälle. In der
Codex-Umgebung lagen weder die Hetzner-Tiingo-Datei noch echte historische HS5RMP-Quotes oder
offizielle Produktunterlagen vor. Deshalb ist **keine historische Derivatrendite berechnet**.
Der maschinenlesbare [Quellenaudit](hebeltrader-hs5rmp-source-audit-v18.json) hält die tatsächlich
geprüften offiziellen Quellen und die verbleibenden Beschaffungswege fest.

Die Auswertung verwendet drei strikt getrennte Modi:

- `OBSERVED_DERIVATIVE`: ausschließlich autorisierte historische Geld-/Briefkurse; ohne Archiv
  bleibt `return_pct=null`.
- `MODELED_DERIVATIVE`: Black-Scholes-Merton-Szenarien. Diese Werte sind Schätzungen und weder
  beobachtete HSBC-Kurse noch ausführbare Transaktionen.
- `UNDERLYING_SIGNAL`: JNJ-Ziele, Stopps, Zeit bis zur Berührung und maximaler Rückgang aus
  Aktien-OHLC. Dieser Modus liefert niemals eine Optionsscheinrendite.

## Ergebnis der Quellenprüfung

HSBC erklärt in seiner [FAQ](https://www.hsbc-zertifikate.de/home/faq/Allgemeines.html), dass
historische Emittentenkurse nicht direkt bereitgestellt werden, und verweist auf das Kursarchiv
der Börse Stuttgart. Für das abgelaufene Instrument wurde kein autorisierter Export gefunden.
Die [Börse Stuttgart](https://www.boerse-stuttgart.de/de-de/fuer-geschaeftspartner/zugang-zu-boersendaten/)
bleibt deshalb der erste Ansprechpartner für einen Einzelinstrument-Pilotexport einschließlich
Zeitstempel, Geld, Brief, Größen, Handelsplatz, Unterbrechungen und Nutzungsrecht.

Das offizielle Deutsche-Börse-Produkt
[Börse Frankfurt Certificates and Warrants](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/spot-markets/B-rse-Frankfurt-Certificates-and-Warrants-1341024)
enthält gehandelte Preise, Best Bid/Ask und Volumen und wird laut Produktseite bis auf Weiteres
ohne Datengebühr angeboten. Zugang, historische Lieferung, Vertrags- und Nutzungskosten sind
damit nicht automatisch kostenfrei. Der
[Delayed File Service](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/Delayed-data)
führt Post-Trade-Dateien, belegt aber keinen historischen BBO-Export für 2025/26. Die offizielle
[Vendorliste](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/vendorlist) nennt unter
anderem ARIVA.DE und baha; historische HS5RMP-Tiefe und Preise unter 100 EUR monatlich müssen
schriftlich bestätigt werden.

Der Original-HEBELTRADER-Beleg liefert WKN, Empfehlungskurs, Ziele, Stopps, Basispreis und
Laufzeit. Er ersetzt kein offizielles Termsheet. ISIN, Bezugsverhältnis, Referenzbörse,
letzter Handelstag, Ausübung, Settlementwährung und FX-Regel bleiben daher ungeprüft.

## Autorisierten Export offline importieren

CSV-Spalten sind `timestamp,bid,ask` sowie optional `bid_size,ask_size,quote_status,last_tradable`.
`quote_status` muss `executable` sein. JSON verwendet dieselben Felder. Die Metadaten aus V1.7
bleiben Pflicht; Rechte, Handelszeiten und Lückenprüfung werden manuell freigegeben. Originalbytes,
Manifest und Index sind SHA-256-gebunden und unveränderlich.

```bash
python -m scanner.hebeltrader.derivatives_cli import-quotes \
  --input /secure/hs5rmp-authorized.csv \
  --metadata /secure/hs5rmp-metadata.json \
  --archive-dir reports/hebeltrader/hs5rmp-quotes \
  --output reports/hebeltrader/hs5rmp-import.json
```

Der Backtest kauft zum ersten zulässigen Briefkurs und verkauft zum beobachteten Geldkurs.
Ziel 1 verkauft 50 Prozent, danach gilt der tatsächliche Brief-Einstieg als Stopp für den Rest.
Kurslücken werden zum ersten beobachteten Geldkurs ausgeführt. Optionale Kapital-, Stückelungs-
und Gebührenannahmen verändern ausschließlich das Cash-Ergebnis. Eine letzte Quote wird niemals
als Verfallsabrechnung interpretiert. Ohne belegten Exit oder Settlement bleibt der Lauf
`open_or_censored` und `return_pct=null`.

Mit `--capital`, `--unit-size`, `--fee-per-order` und `--enforce-quote-size` lassen sich nur
explizit belegte Ausführungsannahmen aktivieren. Fehlt bei erzwungener Größenprüfung die nötige
Ask- oder Bid-Größe, wird der Lauf blockiert.

## Modellanalyse ohne historische HSBC-Quotes

Die optionale Modellanalyse bewertet einen hypothetischen europäischen Call mit
Black-Scholes-Merton. Sie verwendet JNJ-OHLC, tägliche Restlaufzeit, Volatilität, risikofreien
Zins, kontinuierliche Dividendenrendite, USD/EUR-Umrechnung und Bezugsverhältnis. Spread und ein
zusätzlicher Abschlag bei Kurslücken werden je Szenario ausgewiesen. Bei einer Tageskerze, die
zugleich Stopp und Ziel berührt, nimmt das konservative Szenario den Stopp zuerst, das mittlere
Szenario enthält sich eines Ergebnisses und das optimistische Szenario nimmt das Ziel zuerst.

Die Datei
[`hebeltrader-hs5rmp-model-assumptions-v18.example.json`](hebeltrader-hs5rmp-model-assumptions-v18.example.json)
ist bewusst **kein HS5RMP-Termsheet**. Basispreis und Laufzeit stammen aus der Empfehlung;
Bezugsverhältnis, europäische Ausübungsart, konstantes FX-Verhältnis sowie Volatilitäts-, Zins-,
Dividenden-, Spread- und Gap-Werte sind ausdrücklich hypothetisch. Sie müssen für eine
wissenschaftliche Auswertung durch zeitpunktbezogene Quellen oder ein offizielles Termsheet
ersetzt werden. Fehlt ein Pflichtparameter oder dessen Statusbeleg, wird `MODELED_DERIVATIVE`
blockiert, statt einen Wert zu ergänzen.

Aus einer bereits normalisierten Tiingo-Datei läuft die Analyse vollständig offline:

```bash
python -m scanner.hebeltrader.derivatives_cli scenario \
  --underlying reports/hebeltrader/tiingo-pilot-jnj/jnj-normalized-v17.json \
  --assumptions docs/hebeltrader-hs5rmp-model-assumptions-v18.example.json \
  --publication-at 2025-08-05T08:15:00+02:00 \
  --output reports/hebeltrader/tiingo-pilot-jnj/hs5rmp-three-modes.json
```

Das Ergebnis bleibt `training_eligible=false`. Ein modellierter Gewinn darf weder in
`OBSERVED_DERIVATIVE` kopiert noch als historisch erzielte Rendite bezeichnet werden.

## Hetzner-Prüflauf ohne Netzwerkzugriff

Die vorhandene normalisierte Tiingo-Datei wird direkt und schreibgeschützt eingebunden. Erwartete
115 Zeilen, Datumsgrenzen, zwei Dividenden, keine Splits und der gemeldete Manifest-Hash werden vor
dem Modelllauf geprüft. Die Datei dient nur zur zeitlichen Plausibilisierung des JNJ-Basiswerts;
sie darf keinen beobachteten HS5RMP-Preis erzeugen. Bei EOD-Daten beginnt die Auswertung mit der
ersten vollständigen Handelssitzung **nach** dem Publikationstag. Bars am oder nach dem
Laufzeitende werden ausgeschlossen, weil Laufzeitende weder letzte Handelbarkeit noch eine
bestimmte Abrechnung belegt.

Konkreter Serverablauf für die gemeldete Datei mit 115 Handelstagen:

```bash
set -euo pipefail
cd /opt/aktien-chancen-scanner-v5
git switch main
git pull --ff-only origin main
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD muss bereits gesetzt sein}"
docker compose build api

INPUT="$PWD/reports/hebeltrader/tiingo-pilot-jnj/jnj-normalized-v17.json"
ASSUMPTIONS="$PWD/docs/hebeltrader-hs5rmp-model-assumptions-v18.example.json"
REPORT_DIR="$PWD/reports/hebeltrader"
OUTPUT_NAME="hs5rmp-three-modes-v18-$(date -u +%Y%m%dT%H%M%SZ).json"

python3 - "$INPUT" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
b = p["bars"]
assert len(b) == 115, len(b)
assert b[0]["date"][:10] == "2025-08-05"
assert b[-1]["date"][:10] == "2026-01-16"
assert sum(float(x.get("dividend_cash", 0)) != 0 for x in b) == 2
assert all(float(x.get("split_factor", 1)) == 1 for x in b)
assert p["manifest_sha256"] == "0b48d417a5f896740dd138d5621fbb369ba09762c04f84adc7c001195998f075"
print("JNJ-Eingang geprüft: 115 Bars, 2 Dividenden, 0 Splits")
PY

docker run --rm --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$INPUT,dst=/input/jnj-normalized-v17.json,readonly" \
  --mount "type=bind,src=$ASSUMPTIONS,dst=/input/assumptions.json,readonly" \
  --mount "type=bind,src=$REPORT_DIR,dst=/reports" \
  chancen-scanner-v6:local \
  python -m scanner.hebeltrader.derivatives_cli scenario \
    --underlying /input/jnj-normalized-v17.json \
    --assumptions /input/assumptions.json \
    --publication-at 2025-08-05T08:15:00+02:00 \
    --output "/reports/$OUTPUT_NAME"

python3 - "$REPORT_DIR/$OUTPUT_NAME" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
print("Bericht:", sys.argv[1])
for mode, value in r["modes"].items():
    print(mode, value["status"])
    for name, scenario in value.get("scenarios", {}).items():
        print(" ", name, "entry=", scenario["entry_ask"],
              "status=", scenario["status"], "return_pct=", scenario["return_pct"],
              "events=", scenario["events"])
print("Unsicherheiten:", r["modes"]["MODELED_DERIVATIVE"]["caveat"])
PY
```

Der Block benötigt weder Internet noch API-Key und startet weder PostgreSQL noch andere
Compose-Dienste. Immich und PDFs werden nicht eingebunden. Das Ergebnis enthält für jedes
Szenario Einstieg, Status, Ereignisse, gegebenenfalls Ausstieg/Rendite sowie eine isolierte
±10-Prozent-Sensitivität für Volatilität, Bezugsverhältnis, FX und Spread. Dividendenereignisse
werden offengelegt; die BSM-Bewertung verwendet weiterhin die ausdrücklich hypothetische
kontinuierliche Dividendenrendite des jeweiligen Szenarios.

Danach werden Produktunterlagen und Quoteexport privat archiviert, die Metadaten von einem
Reviewer freigegeben und `derivative-data backtest` ausgeführt. Der JSON-Ausgang bleibt privat,
wenn die Datenlizenz keine Veröffentlichung erlaubt. Nur Hash, Coverage-Kennzahlen und Ergebnis
dürfen entsprechend dem bestätigten Nutzungsrecht in einen Bericht übernommen werden.

## Skalierung auf 118 Empfehlungen

`prioritize_acquisition` ordnet jede Empfehlung ausschließlich anhand von Produkt- und
Quoteevidenz in `verified_executable_quotes`, `restricted_archive`, `terms_only` oder
`insufficient_data` ein. Verzeichnisnamen `all`, `half` und `fail` werden entfernt und niemals
als Trainings- oder Erfolgslabel verwendet. Vor einem Datenkauf wird zuerst die erreichbare
Einzelprodukt-Coverage bei Stuttgart gemessen, danach ein Angebot der Deutschen Börse und erst
dann ein Vendorangebot für alle 118 Instrumente verglichen. Kein Auftrag oder Abonnement ist
durch diese Dokumentation genehmigt.

Die reproduzierte, lesende Auswertung der vorhandenen 118er-Inventardaten steht als
[`hebeltrader-derivative-acquisition-v18.json`](hebeltrader-derivative-acquisition-v18.json)
und CSV mit SHA-256-Manifest bereit. Ergebnis: 118 von 118 bleiben streng
`insufficient_data`, weil weder offiziell freigegebene vollständige Produktbedingungen noch
autorisierte Quotehistorien in der Codex-Umgebung vorlagen. Vorhandene Parserfelder werden als
solche ausgewiesen und nicht als offizielle Produktverifikation umgedeutet.

Ein neuer Bestand wird ohne API- oder Datenbankzugriff priorisiert:

```bash
python -m scanner.hebeltrader.derivatives_cli prioritize \
  --input /secure/recommendation-evidence.json \
  --output-prefix reports/hebeltrader/derivative-acquisition-v18
```
