# Historische HEBELTRADER-Analyse – Entwurf zur Prüfung

## Ziel und bestehende Architektur

Historische Empfehlungen aus dem lokalen Bestand von 118 PDFs strukturiert und
nachvollziehbar erfassen. Keine Trades, keine kostenpflichtigen Dienste, kein
produktives Deployment. Der Import ergänzt das vorhandene Paket `scanner`, die
SQLAlchemy-Basis, Alembic, PostgreSQL und das bestehende Anwendungsimage.
Krypto-Worker und seine Signallogik bleiben unverändert.

Die vorhandene Testsuite besteht vor Änderungen mit 50 Tests; zwei
PostgreSQL-Tests wurden ohne konfigurierte Testdatenbank übersprungen.
`origin/main` enthält bereits das zusammengeführte Phase-1-Fundament.

## Quellenbefund und Konsequenzen

Über den bereits autorisierten Google-Drive-Connector wurden der HEBELTRADER-
Ordner mit seinen Kategorien und eine Originalausgabe untersucht. Die Anzahl
118 wurde noch nicht durch vollständige Auflistung verifiziert.

Die geprüfte Ausgabe unterscheidet Derivat und Basiswert: verschiedene WKNs,
Preise, Kursziele und Stopps stehen auf unterschiedlichen Seiten. Der Emittent
ist nicht zwingend ausdrücklich angegeben. Eine Kursindikation mit Uhrzeit ist
kein Nachweis der Veröffentlichungsuhrzeit. Wiederholte Seitenköpfe und allgemeine
Anlagegrundsätze dürfen keine zusätzlichen Empfehlungen erzeugen.

Original-PDFs und Originalvolltexte werden nicht in das öffentliche Repository
übernommen. Automatisierte Beispieldateien sind vollständig synthetisch.

## Technischer Ansatz

Empfohlen: lokale, regelbasierte Extraktion mit `pdfplumber` für Text, Wörter mit
Positionen und Tabellen. Das vermeidet externe Verarbeitungskosten und erhält
prüfbare Belege. Eine reine Volltext-RegEx-Lösung wäre kleiner, verliert aber
räumliche Zuordnung. Eine generative Extraktion wäre aufwendiger und schlechter
reproduzierbar; sie ist nicht Bestandteil dieses Moduls.

Eigenes Unterpaket `scanner/hebeltrader/` mit getrennten Verantwortlichkeiten:
PDF-Lesen, Layout-/Feldparser, Qualitätsprüfung, Import/Persistenz, Analyseexport
und CLI. Einstellungen werden wie bisher über Umgebungsvariablen geladen.
Neue Tabellen werden über eine additive Alembic-Migration eingeführt.

## Datenmodell und Nachvollziehbarkeit

- **Quelldokument:** SHA-256 der Originalbytes, Dateiname, relativer Quellpfad,
  Dateigröße, Importzeit, Extraktorversion, Status und ursprüngliche Kategorie.
  Mehrere Fundorte derselben Datei bleiben als Herkunftsbezüge erhalten.
- **Ausgabe:** verifiziertes oder ungeklärtes Veröffentlichungsdatum,
  Ausgabenummer/Jahr und Verknüpfung zu ihren Quelldokumenten. Fehlende oder
  widersprüchliche Metadaten werden nicht aus Dateizeitstempeln ergänzt.
- **Empfehlung:** Aktie/Basiswert, getrennte WKN/ISIN für Aktie und Derivat,
  Produktart, expliziter Emittent, Basispreis, Laufzeit/Fälligkeit,
  Einstieg-/Indikationskurs des Derivats, Omega/Hebel und dessen Bezeichnung,
  Aktienkurs, jeweils getrennte Ziele und Stopps für Aktie und Derivat, CRV,
  Währungen sowie fundamentale und charttechnische Hinweise.
- **Extraktionsbelege:** Originalseite, Textausschnitt beziehungsweise Tabellen-
  zelle und Position, Rohwert, normalisierter Wert und Parserregel je Feld.
- **Prüfbefunde:** fehlende Werte, Konflikte, ungültige Kennungen, zweifelhafte
  Zahlen/Datumswerte, fehlender Text/OCR-Bedarf und unerkannte Layouts mit
  Dokument-/Seiten-/Feldbezug. Status `needs_review` statt erfundener Werte.
- **Importlauf:** Start/Ende, Dateien gefunden/importiert/übersprungen/fehlgeschlagen,
  Empfehlungen und Prüffälle; maschinenlesbare Zusammenfassung und Fehlerprotokoll.

Numerische Werte werden als Decimal gespeichert; deutsche Dezimal- und
Tausendertrennzeichen werden explizit behandelt. Laufzeitangabe und Fälligkeit
bleiben unterscheidbar. Ein genannter aktueller Kurs wird als Indikation
gekennzeichnet und nicht als nachgewiesener Ausführungskurs ausgegeben.

## Wiederholbare Imports und Konflikte

Eine Datei wird anhand ihrer Prüfsumme erkannt, nicht allein anhand ihres Namens.
Ausgaben erhalten eindeutige fachliche Identitäten, sofern diese sicher lesbar
sind. Identische erneute Imports erzeugen keine zusätzlichen Empfehlungen.
Abweichende Dokumentversionen derselben Ausgabe überschreiben keine vorhandenen
Werte stillschweigend: Varianten und Konflikte werden mit Quellenbezug zur
Prüfung erhalten und aus ungeprüften Analyseexporten ausgeschlossen.

Jede Datei wird transaktional verarbeitet. Ein beschädigtes PDF blockiert den
restlichen Ordner nicht. Scan-PDFs ohne Text werden mit OCR-Bedarf protokolliert;
automatisches OCR ist zunächst nicht Bestandteil der akzeptierten Extraktion.

`all`, `half` und `fail` sind ausschließlich unverifizierte Herkunftskategorien.
Sie werden weder als Erfolg noch als Verlust interpretiert und gehen nicht in
Signalmerkmale oder berechnete Erfolgsquoten ein.

## Import und Docker

Ein CLI-Befehl importiert rekursiv aus einem konfigurierbaren lokalen PDF-Ordner.
Ein optionaler Compose-Service im Profil `analysis` verwendet das vorhandene
Image und Backend-Netzwerk, startet nicht im normalen Scanner-Betrieb und bindet
den Quellordner nur lesend ein. Keine neuen Host-Ports und keine Änderungen an
Immich. Berichte werden in einen gesonderten konfigurierbaren Ausgabeordner
geschrieben. Originalbestände und Berichte bleiben außerhalb von Git.

Google Drive ist keine implizite Voraussetzung: Ein autorisiert bereitgestellter
lokaler Export oder sicherer Read-only-Mount reicht aus. Der verbundene Connector
darf für Tests an ausgewählten Originalen verwendet werden. Keine anonymen
Freigaben, fest kodierten Tokens oder Zugangsdaten im Repository und keine
automatische neue Drive-Autorisierung im Importprozess.

## Grundlage für historische Erfolgsauswertung

Extrahierte Veröffentlichungsinformationen, lokale Importzeit und Kursindikation
bleiben getrennt. Ohne nachgewiesene Veröffentlichungsuhrzeit ist das Dokument
frühestens nach Ende seines Veröffentlichungstags in Europe/Berlin für einen
konservativen zeitpunktbezogenen Export zugelassen; diese Annahme wird markiert.
Fehlende Veröffentlichungstage schließen einen Datensatz aus einem solchen
Export aus. Historische Daten sind keine damals lokal beobachteten Live-Signale.

Ein Analyseexport trennt damalige Empfehlungsmerkmale von späteren Outcomes,
Herkunftskategorien und Importmetadaten. Nur freigegebene, quellenbelegte Datensätze
werden als modellgeeignet ausgewiesen. Die eigentliche Rendite-/Erfolgsberechnung
benötigt zusätzlich zeitgestempelte Kursreihen, Ausführungsregeln und die Behandlung
mehrdeutiger Intraday-Ziel-/Stoppfolgen; sie wird vorbereitet, nicht vorgetäuscht.

## Abnahme und Tests

Synthetische PDFs prüfen vollständige und fehlende Felder, getrennte Instrumente,
Tabellen, mehrere Empfehlungen, widersprüchliche Angaben, wiederholte Kopfzeilen,
Scan-/defekte Dateien und deutsche Zahlenformate. Datenbanktests prüfen Original-
zuordnung, Wiederholungsimporte, Dateikopien/Umbenennungen und Versionskonflikte.
Analyseexporttests prüfen den Zeitbezug und den Ausschluss von Kategorien und
späteren Outcomes. Migrationen werden auf SQLite und einer wegwerfbaren
PostgreSQL-Datenbank geprüft; anschließend läuft die gesamte bestehende Suite.

Docker-Build, Compose-Profil und ein echter CLI-Import mit Beispieldateien werden
geprüft. README und eigene Moduldokumentation enthalten lokale Startbefehle,
Deployment-Vorbereitung, Import, Berichte, manuelle Prüfung und Grenzen der
Extraktionsqualität. Ein Pull Request gegen `main` fasst Änderungen und tatsächlich
ausgeführte Testergebnisse zusammen. Kein produktives Deployment.
