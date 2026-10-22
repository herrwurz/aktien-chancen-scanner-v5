# HEBELTRADER Parser V2.1

## Diagnose und Änderungen

Die fünf gemeldeten Ausgaben enthielten bereits eine korrekt erkannte Tabelle.
Zusätzlich erzeugten Fließtextanfänge wie „Optionsschein …“ und die Überschrift
„OPTIONSSCHEIN VS. AKTIE“ jeweils eine falsche Empfehlung ohne WKN und Kurs.
V2.1 verlangt eine vollständige Produktüberschrift mit benachbarten
Instrumenten- und Kurslabels. Zweizeiliges „TURBO UNLIMITED / LONG“ wird erkannt.
Die anhand der WKN-Spalte bestimmte Spaltengrenze wird auch für Folgeseiten
verwendet; Haupttext und rechte Informationsspalte bleiben getrennt.

Akt. Kurs, Akt. Kurs**, Aktueller Kurs und Einstiegskurs werden unterstützt.
Explizites Open End wird als Laufzeittext gespeichert, ohne ein Enddatum zu
erfinden. Widersprüchliche Angaben bleiben prüfpflichtig. Emittenten werden
weiterhin ausschließlich aus expliziten Quellenangaben übernommen.

Original-CRV steht unverändert in `crv`. Abgeleitete Werte stehen separat in
`evidence._calculated_crv` sowie `calculated_crv` bei Inspect/Export. Je Kursziel
wird `(Ziel − Kurs)/(Kurs − Stopp 1)` berechnet: nur mit Instrumentenidentität,
belegten, eindeutigen Preisen gleicher expliziter Währung und
`0 <= Stopp < Kurs < Ziel`. Formel, Version, Eingaben und Quellenbelege werden
mitgespeichert. Keine Währungsumrechnung und kein Ersatz fehlender Original-CRV.
Diese Kennzahl beschreibt zitierte Kurse; sie ist kein historischer Erfolgsnachweis.

## Vorher-Nachher-Prüfung

Am 22.10.2026 wurden alle 118 Original-PDFs über einen bestehenden autorisierten
Drive-Zugang lokal gelesen. Hetzner und Drive wurden nicht verändert. Derselbe
Bestand wurde mit `origin/main` (84b2fe3) und V2.1 erneut extrahiert. Originale
und Volltext-Snapshots sind nicht im Repository; enthalten sind synthetische
Regressionstests und der aggregierte [JSON-Bericht](hebeltrader-v21-quality.json).
Die synthetischen PDFs reproduzieren die Layoutprobleme, ihre übrigen Zahlen
sind ausdrücklich erfunden. Alle fünf genannten Originale wurden zusätzlich
lokal erfolgreich geprüft.

| Merkmal | Vorher | V2.1 |
|---|---:|---:|
| PDFs / Extraktionsfehler | 118 / 0 | 118 / 0 |
| Empfehlungen | 123 | 118 |
| Derivat-WKN vorhanden | 118/123 | 118/118 |
| Derivatkurs vorhanden | 118/123 | 118/118 |
| Original-CRV vorhanden | 50/123 | 88/118 |
| Emittent vorhanden | 0/123 | 0/118 |
| Berechnete CRV je Ziel 1 / 2 | 0 / 0 | 118 / 118 |

2618 bereits belegte Feldwerte identifizierbarer Empfehlungen bleiben erhalten;
kein geänderter Wert im Vergleich. Fünf unidentifizierte Scheinempfehlungen
entfallen. Produktbezeichnungen sind von diesem Werterhaltvergleich ausgenommen.
Die gemeldete Serverbaseline nennt 77 fehlende CRV; der reproduzierte lokale
Ausgangslauf ergibt 73. Die Zahlen werden nicht gleichgesetzt. Ein Vergleich
mit dem tatsächlichen Serverdatenbestand bleibt ein gesonderter Betreiberlauf.

Verbleibend: 118 fehlende Emittenten, 30 fehlende Original-CRV, vier fehlende
Aktien-WKN; jeweils zwei fehlende Aktienkurse, erste Ziele und Stopps 1/2;
drei fehlende zweite Aktienziele (eins wegen ungültiger Angabe). Zwei Dokumente
haben eine mehrdeutige Aktiensektion. Drei fehlende feste Enddaten sind bei
Open-End-Produkten sachgerecht und werden nicht als fehlende Laufzeit markiert.
Alle Feldvollständigkeiten und Prüfhinweiszahlen stehen im JSON-Bericht.

## Sicherer Vergleich vorhandener Daten

Keine neue Schema-Migration. Ein normaler Wiederholungsimport überspringt
bekannte SHA-256-Dateien auch bei alter Parser-Version. Bestehende Datensätze,
manuelle Korrekturen und Freigaben werden nicht durch V2.1 ersetzt. Es gibt
bewusst keinen automatischen Reparse-/Übernahmebefehl für Betriebsdaten.

```bash
# Aus dem Repository, mit vorhandener sicherer DATABASE_URL-Konfiguration:
python -m scanner.hebeltrader quality --output /tmp/hebeltrader-v21-quality.json
# Oder im bereits separat konfigurierten Compose-Projekt:
docker compose --profile analysis run --rm --no-deps pdf-import \
  python -m scanner.hebeltrader quality --output /reports/v21-quality.json
```

`quality` liest gespeicherte Originalbytes, prüft deren SHA und vergleicht die
aktuelle Extraktion mit gespeicherten Feldern. PostgreSQL verwendet eine
READ-ONLY-Transaktion; die Anwendung führt weder Commit noch DDL aus. Der Bericht
enthält Feldvollständigkeit, Prüfhinweise, Werterhalt und abweichende Kandidaten;
Abweichungen können auch absichtliche manuelle Korrekturen sein. Ausgabedateien
werden mit Modus 0600 neu angelegt und niemals überschrieben. Bei
Extraktionsfehlern Rückgabecode 2. Der Lauf kann bei großen Beständen dauern.
Eine neue leere Testdatenbank kann separat mit den bestehenden dokumentierten
Migrationen und Importbefehlen aufgebaut werden; niemals produktive Daten
löschen, um ein Neuparsen zu erzwingen.

Start-/Deployment-Konfiguration siehe [hebeltrader.md](hebeltrader.md).
Dieser PR führt kein Deployment, keine Produktionsmigration und keine
Änderungen vorhandener Daten oder anderer Docker-Projekte aus.

## Ausgeführte technische Prüfungen

Am 22.10.2026: **102 Tests erfolgreich**, einschließlich Migrationstests gegen
PostgreSQL 17.6 in einem ausschließlich dafür erzeugten lokalen Testcontainer.
Befehl: `TEST_DATABASE_URL=… .venv/bin/python -m pytest -q`.
`ruff check .`, `ruff format --check .` und `git diff --check` erfolgreich.
Docker-Image `chancen-scanner-v6:v21-test` erfolgreich gebaut; CLI-Hilfe im
Container geprüft. Unabhängiges Code-Review: keine verbleibenden blockierenden
Befunde. Original-PDF-Prüfung und aggregierte Zahlen siehe oben.
