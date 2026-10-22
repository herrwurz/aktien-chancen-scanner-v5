# V1.7: HS5RMP als primäres Pilotinstrument und Tiingo für den Basiswert

Stand der Quellenprüfung: 22.10.2026. Diese Erweiterung trennt strikt:

1. ausführbare Geld-/Briefquotierungen des empfohlenen Calls HS5RMP,
2. Produktstammdaten und Abrechnungsbedingungen aus Originalunterlagen,
3. tägliche JNJ-Basiswertdaten von Tiingo oder EODHD.

Nur die erste Datenart kann eine historische Derivatrendite tragen. JNJ-OHLCV, Omega,
implizite Volatilität oder Black-Scholes-Werte ersetzen niemals beobachtete Optionsschein-
Quotes. Der primäre Erfolgsmaßstab ist daher
`verified_executable_HS5RMP_bid_ask_return`. Die Aktienauswertung bleibt ein gesondertes,
hypothetisches Forschungsmodell.

## Tatsächlicher Abnahmestand

Im Checkout lagen weder die echte Tiingo-Datei vom Hetzner-Server noch ein historischer
HS5RMP-Quoteexport oder die Original-Produktunterlagen vor. Deshalb wurde kein echter
Derivate-Backtest gerechnet. Die im Auftrag genannten 115 Tiingo-Handelstage und JNJ-Werte
sind als vom Betreiber gemeldeter Realtest dokumentiert, aber noch nicht durch diese Pipeline
reproduziert. Testfixtures tragen ausdrücklich synthetische Werte.

Aus der Originalempfehlung sind WKN `HS5RMP`, Empfehlungskurs 0,17 EUR, Ziele 0,70/2,30 EUR
und Fälligkeit 16.01.2026 belegt. ISIN, Emittent, Bezugsverhältnis, Basispreis, letzter
Handelstag und Abrechnungsbedingungen bleiben bis zum hashgebundenen Import der
Original-Produktunterlagen ungeprüft. Insbesondere wird keine ISIN aus der WKN errechnet und
kein Handelstag aus der Fälligkeit abgeleitet.

## Recherche zu echten historischen Quotes

- [HSBC FAQ](https://www.hsbc-zertifikate.de/home/faq.html): HSBC gewährt Anlegern keinen
  direkten Zugriff auf historische Emittentenkurse und verweist auf das Kursarchiv der Börse
  Stuttgart. Damit ist das Emittentenarchiv kein verfügbarer API- oder Exportpfad.
- [Börse Stuttgart](https://www.boerse-stuttgart.de/de-de/fuer-geschaeftspartner/zugang-zu-boersendaten/)
  beschreibt Marktdatenzugang; Einzelinstrumentseiten bieten „Historische Preise / Taxen“.
  Ein öffentlicher, dokumentierter Massen-API-Zugang mit eindeutig geklärten
  Weiterverwendungsrechten für den vollständigen HS5RMP-Zeitraum wurde nicht gefunden.
  Ein Export muss daher mit Herkunft, Nutzungsrecht und Vollständigkeit separat geprüft werden.
- [Deutsche Börse: Börse Frankfurt Certificates and Warrants](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/spot-markets/B-rse-Frankfurt-Certificates-and-Warrants-1341024)
  nennt gehandelte Preise, Best Bid/Ask und Volumina für Zertifikate und Optionsscheine.
  „Kostenfrei bis auf Weiteres“ beschreibt das Informationsprodukt, nicht automatisch eine
  freie Redistribution historischer Rohdaten.
- [Deutsche Börse Market Data](https://www.cashmarket.deutsche-boerse.com/cash-en/Data-Tech/statistics/market-data)
  verweist für historische Börsendaten auf den Data Shop und für Datenbezug auf lizenzierte
  Produkte/Vendoren. Die öffentliche
  [Handelshistorie](https://live.deutsche-boerse.com/derivatives/historical-quotes/trade-history)
  nennt nur die vorherigen vier Wochen und liefert keine vollständige 2025/26-Bid/Ask-Reihe.
- Die inzwischen abgelaufenen HS5RMP-Einzelseiten bei Frankfurt und Stuttgart waren am
  Prüftag nicht mehr verfügbar. Deshalb sind Stammdaten aus Suchtreffern oder ähnlichen
  HSBC-Produkten kein Produktbeleg für HS5RMP.

Ein belastbarer nächster Schritt ist eine schriftlich lizenzierte Exportauskunft bei Börse
Stuttgart bzw. Deutsche Börse für WKN HS5RMP, 05.08.2025 bis letzter Handelstag, inklusive
Zeitstempel, Venue, Bid, Ask, Quotegröße und Quotierungsunterbrechungen. Ohne diesen Export
bleibt `return_pct=null`.

## Offline-Importer und Derivate-Backtest

Die Eingabedatei ist ein JSON-Array mit streng aufsteigenden, zeitzonenbehafteten
Zeitstempeln, `bid`, `ask` und optional `last_tradable`. Die Metadatendatei enthält WKN,
ISIN, MIC, Zeitzone, Währung, Quellenlink, Lizenztext, Abrufzeit, Abdeckungsgrenzen und
`quote_kind=executable_bid_ask`. Der Import validiert Bid ≤ Ask, Zeitraum, Zeitzone und
Reihenfolge. Originalbytes, Manifest und Importindex werden exklusiv mit SHA-256 geschrieben;
ein abweichender Wiederholungsimport wird abgelehnt.

```bash
python -m scanner.hebeltrader.cli derivative-data import-quotes \
  --input /pfad/hs5rmp-quotes.json \
  --metadata /pfad/hs5rmp-quote-metadata.json \
  --archive-dir /pfad/immutable-hs5rmp-archive \
  --output /pfad/hs5rmp-import.json
```

Der Backtest startet erst bei manuell freigegebenen, quellgebundenen Produktstammdaten. Er
verwendet den ersten zulässigen Briefkurs als Einstieg und ausschließlich Geldkurse für
Verkäufe. Ziel 1 verkauft 50 %, danach liegt der Stopp für den Rest am tatsächlichen
Brief-Einstieg; Ziel 2 verkauft den Rest. Die 20-Tage-Regel ist nur ein Verlustausstieg:
Nach Ablauf der explizit geprüften Kalender- oder Handelstagseinheit wird nur verkauft, wenn
der beobachtete Geldkurs unter dem Einstieg liegt. Gebühren bleiben unbekannt. Fehlende Quotes,
Quotierungsunterbrechungen, letzter Handelstag und Abrechnung müssen aus der Quelle belegt
werden; sonst bleibt der Lauf offen/zensiert oder gesperrt.

```bash
python -m scanner.hebeltrader.cli derivative-data backtest \
  --archive-dir /pfad/immutable-hs5rmp-archive \
  --manifest-sha256 MANIFEST_SHA \
  --product-terms /pfad/hs5rmp-product.approved.json \
  --rules /pfad/hs5rmp-rules.approved.json \
  --publication-at 2025-08-05T00:00:00+02:00 \
  --output /pfad/hs5rmp-backtest.json
```

## Tiingo: Basiswertprovider, kein Optionsscheinprovider

[Tiingo EOD-Dokumentation](https://api.tiingo.com/documentation/end-of-day) beschreibt rohe
und bereinigte OHLCV-Werte sowie `divCash` und `splitFactor`. Die Implementierung archiviert
die unveränderte Antwort und hält rohe und bereinigte Werte getrennt. Ziele und Stopps nutzen
nur rohe OHLC-Werte. Ein eigenständiger historischer Handelskalender bleibt Pflicht; er wird
nicht aus vorhandenen Zeilen erfunden. Tiingo liefert hier Aktien-EOD-Daten und keine deutschen
HS5RMP-Bid/Ask-Quotes.

`compare_daily_coverage` vergleicht je Provider gelieferten Zeitraum, Zeilenzahl, gemeinsame
Tage und fehlende Tage gegenüber der Vereinigungsmenge. Es verbindet die Reihen nicht und
behauptet keine Kalender-Vollständigkeit. Ein Tiingo→EODHD-Fallback bleibt gesperrt, bis
Identität, MIC, Währung und Corporate Actions für beide Archive geprüft sind.

[Tiingos Nutzungsübersicht](https://www.tiingo.com/documentation/general/overview) beschränkt
Basic/Power auf persönliche bzw. interne Nutzung und verbietet Redistribution. Deshalb werden
echte Preisbytes nicht in GitHub-Berichte aufgenommen. Der Token kommt nur aus
`TIINGO_API_TOKEN`; URL, Manifest, Fehlerausgabe und Nutzungsjournal enthalten ihn nicht.

Die vorhandene Hetzner-Datei wird ohne Netzwerkzugriff zunächst unveränderlich aufgenommen.
`--retrieved-at` ist der belegte ursprüngliche Abrufzeitpunkt, nicht der Importzeitpunkt:

```bash
python -m scanner.hebeltrader.cli tiingo import \
  --input /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-pilot-jnj/jnj-historical.json \
  --cache-dir /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-cache \
  --output /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-import.json \
  --symbol JNJ --from 2025-08-05 --to 2026-01-16 \
  --retrieved-at ORIGINAL_ABRUFZEIT_MIT_ZONE
```

Danach ist der Replay vollständig offline:

```bash
python -m scanner.hebeltrader.cli tiingo replay \
  --cache-dir /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-cache \
  --manifest-sha256 MANIFEST_SHA \
  --output /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-pilot-jnj/jnj-normalized.json
```

Eine neue Abfrage benötigt gemeinsam `--allow-network`,
`--authorize-provider-usage`, ein positives `--max-requests` und einen deklarierten
Monatsbetrag ≤ 100 EUR. Dieser Befehl ist nur eine Betriebsanleitung und wurde nicht ausgeführt:

```bash
TIINGO_API_TOKEN="$(< /root/scanner-secrets/tiingo.key)" \
python -m scanner.hebeltrader.cli tiingo collect \
  --cache-dir /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-cache \
  --output /opt/aktien-chancen-scanner-v5/reports/hebeltrader/tiingo-collection.json \
  --symbol JNJ --from 2025-08-05 --to 2026-01-16 \
  --allow-network --authorize-provider-usage --max-requests 1 --monthly-total-eur 0
```

Der Befehl bucht kein Abo; eine kostenpflichtige Nutzung benötigt separate Freigabe.

## Verbleibende Abnahme auf Hetzner

1. Tiingo-Datei unverändert hashen und offline archivieren; 115 Zeilen, Grenzen,
   Roh-/Adjusted-Felder, Splits/Dividenden und Lücken gegen einen unabhängigen XNYS-Kalender
   prüfen.
2. HS5RMP-Original-Produktdokumente archivieren und alle Stammdaten mit Seiten-/Feldbeleg,
   Reviewer und Zeitstempel freigeben.
3. Lizenzierten HS5RMP-Bid/Ask-Export importieren und Quotevollständigkeit, Handelszeiten,
   Unterbrechungen, Größen, letzten Handelstag sowie Abrechnung prüfen.
4. Erst dann den Derivate-Backtest ausführen. Das Ergebnis bleibt gebührenexklusiv und
   `training_eligible=false`.

