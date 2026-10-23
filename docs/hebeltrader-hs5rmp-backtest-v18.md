# Scanner V6 V1.8: HS5RMP-Backtest

Stand: 23.10.2026. V1.8 erweitert die V1.7-Pipeline für autorisierte CSV- und JSON-Exporte,
Quotegrößen, Spreads, Lücken, Stückzahlen, Gebühren und zensierte Verfallsfälle. In der
Codex-Umgebung lagen weder die Hetzner-Tiingo-Datei noch echte historische HS5RMP-Quotes oder
offizielle Produktunterlagen vor. Deshalb ist **keine historische Derivatrendite berechnet**.
Der maschinenlesbare [Quellenaudit](hebeltrader-hs5rmp-source-audit-v18.json) hält die tatsächlich
geprüften offiziellen Quellen und die verbleibenden Beschaffungswege fest.

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
python -m scanner.hebeltrader.cli derivative-data import-quotes \
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

## Hetzner-Prüflauf ohne Netzwerkzugriff

Die vorhandene Tiingo-Datei wird mit dem V1.7-Befehl `tiingo import` unverändert archiviert.
Erwartete 115 Zeilen und Datumsgrenzen müssen am Server gemessen werden. Die Datei dient nur zur
zeitlichen Plausibilisierung des JNJ-Basiswerts; sie darf kein HS5RMP-Ereignis und keinen
Optionsscheinpreis erzeugen.

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
python -m scanner.hebeltrader.cli derivative-data prioritize \
  --input /secure/recommendation-evidence.json \
  --output-prefix reports/hebeltrader/derivative-acquisition-v18
```
