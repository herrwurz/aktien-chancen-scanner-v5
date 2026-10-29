# HEBELTRADER als primäre Scannerfunktion

Stand: 28.10.2026. Der Startbildschirm `/` dient der Teaseridentifikation. Der bisherige
Marktscanner bleibt unter `/market-scanner` erhalten. PR #27 wird nicht eingebunden.

## Durchgehender Ablauf

Text, öffentliche URL, Überschrift, Herausgeber, optionaler Veröffentlichungszeitpunkt,
Werberendite und Screenshot/PDF werden getrennt erfasst. Originaleingabe, extrahierter Text,
Quellen und Rangliste landen in einem eigenen Verzeichnis je Lauf. Der neue Ablauf verwendet
die vorhandene OCR/PDF-Extraktion, Hinweisextraktion und Evidenzmatrix, nicht den alten
Adapter mit sechs synthetischen Unternehmen. Suchergebnisse dienen nur der Entdeckung;
Bestätigung erfordert die abgerufene Originalseite. Es gibt keinen 100-Aktien-Vorfilter.

Alle Kandidaten werden mit derselben Matrix verglichen. Konkrete Transaktionen und
periodengleiche Finanzzahlen wiegen stärker als Branchenfloskeln. Übernahme, Beteiligung und
Partnerschaft sind unterschiedliche Hinweise. Finanzzahlen benötigen einen ausdrücklich
passenden Unternehmensbezug. Harte Widersprüche entkräften eine Zuordnung. Die Ausgabe
enthält Top 3, alle geprüften Alternativen, Quellen, offene Hinweise und Gegenargumente.

Eine Identifikation erfordert mindestens fünf datierte, relevante Gegenkandidaten, zwei
spezifische Primärbelege, einen belegten Ticker, ausreichenden Evidenzabstand und aktive
Falsifikationsrecherche. Fehlende Voraussetzungen ergeben **nicht identifiziert**. Der
Evidenzscore ist keine Wahrscheinlichkeit. Diese konservativen Regeln ersetzen keine
manuelle Prüfung und sind noch nicht unabhängig an echten Blindfällen validiert.

## Reproduzierbarer Einzellauf

Im Repository mit installierten Abhängigkeiten:

```bash
python -m scanner.hebeltrader.detective.investigate_cli analyze \
  --text-file /pfad/teaser.txt --headline 'Originalüberschrift' \
  --publisher 'Herausgeber' --publication-at '2026-10-28T08:00:00+01:00' \
  --allow-network --max-requests 40 --primary-domains /pfad/primary-domains.json \
  --root data/hebeltrader-detective
```

Alternativ `--url https://...` statt Texteingabe. Ohne `--allow-network` erfolgt kein
Netzwerkzugriff. `--packet /pfad/quellen.json` erlaubt einen dokumentierten Quellenimport,
ist aber kein unabhängiger Blindtest. Das JSON ist eine Liste mit `url`, `title`, `text`,
`company_name`, optional `ticker`, `source_kind`, `published_at` und `retrieved_at`.
Operatorimporte sind eine Vertrauensgrenze: Die Software verifiziert nicht nachträglich,
ob vom Operator behauptete Herkunft und Zeitstempel stimmen.

`primary-domains.json` ordnet **exakte geprüfte Hostnamen** dem Unternehmen zu:
`{"investor.beispielunternehmen.de": "Beispielunternehmen AG"}`. Keine pauschale
Suchtreffer-Whitelist verwenden. Unbekannte Quellen bleiben Sekundärquellen; fehlende
Unternehmensidentität oder Zeitzone wird nicht geschätzt. Domains und Belege müssen vor
Verwendung tatsächlich geprüft werden. Die Recherche extrahiert derzeit nur explizite
HTML-/JSON-LD-Identitäten und deutsch/englische Muster. Sie ist keine vollständige weltweite
Unternehmensdatenbank und kann relevante Kandidaten übersehen.

Die API ist `POST /api/hebeltrader/investigate`; ohne Netzfreigabe bleibt sie offline.
Für Netzrecherche sind `DETECTIVE_PUBLIC_ALLOW_NETWORK=true` und der vorhandene
`DETECTIVE_LIVE_API_TOKEN` erforderlich. Der Browser übermittelt diesen nur als
`X-Research-Authorization`, nicht im archivierten Eingabe-JSON. Die optionalen Pfade
`DETECTIVE_PRIMARY_DOMAINS` und `DETECTIVE_PRODUCT_ISSUERS` sind Betreiberkonfiguration.
Keine Schlüssel ins Repository oder in Berichte schreiben.

## Öffentliche Teaser regelmäßig prüfen

```bash
python -m scanner.hebeltrader.detective.investigate_cli watch \
  --allow-network --once --max-requests 40 --root data/hebeltrader-detective
```

Ohne `--once` läuft die Schleife mit `--interval-seconds 3600` (Minimum 300).
`--query` kann mehrfach öffentliche Suchabfragen konfigurieren. Start und Quellenwahl
bleiben ausdrücklich beim Betreiber; diese Änderung startet keinen Dienst und nimmt kein
Deployment vor. Robots-Regeln, Login-/Paywall-Metadaten, öffentliche HTTPS-Adressen,
Antwortgrößen und Abrufbudget werden geprüft. Gesperrte Suchquellen werden als Datenlücke
ausgewiesen, nicht umgangen. Keine kostenpflichtigen APIs oder KI-Aufrufe.

Originale werden archiviert, URL und Publikationszeit dedupliziert. Neubewertung erfolgt
frühestens nach 24 Stunden. Benachrichtigungen entstehen nur bei neuem Teaser oder
wesentlich verbesserter Evidenz; ein gespeicherter Höchststand verhindert Wiederholungen.
Das ist ein **lokaler Postausgang**, sichtbar auf der Startseite und unter
`GET /api/hebeltrader/updates`. E-Mail, Telegram oder andere externe Zustellung sind
nicht eingerichtet. Ein Marketinginterview mit bloßem Anzeigenfuß ist kein neuer Aktienteaser.

## Historie, Blindtests und Integrität

Die zentrale Fallhistorie bleibt [Identifikationsregeln](hebeltrader-identification-rules.md).
[Maschinenlesbares Inventar](hebeltrader-case-inventory.json) erfasst alle 18 Fälle,
einschließlich ADI/LSCC, CRM/Zoom, JPM/GS, JNJ und des ungelösten Williams-Falls.
Keine vollständigen Originaltexte, exakten Veröffentlichungszeiten oder ursprünglichen
Top-3-Ranglisten sind im Register verfügbar. Daraus entstehen keine 18 Blindtests.

```bash
python -m scanner.hebeltrader.detective.investigate_cli inventory
python -m scanner.hebeltrader.detective.investigate_cli evaluate \
  --rankings /pfad/analyses/LAUF/ranking.json --labels /getrennt/aufloesung.json
```

Die Analyse liest dieses Register und Auflösungsdateien **nicht**. `--labels` während
Analyse oder Monitoring wird abgewiesen. Ein historischer Blindlauf benötigt
`--historical-blind`, ein bereits archiviertes Quellenpaket und einen exakten Teaserzeitpunkt;
Live-Recherche ist dabei ausgeschlossen. Später entdeckte Quellen gehören nicht in diesen
historischen Suchkontext. Auflösungen werden erst nach exklusivem Einfrieren der Rangliste
mit SHA256 zur Bewertung geladen. Eingaben und Lösungshistorie müssen auch auf Ebene des
Testoperators getrennt bleiben; ein selbst deklariertes Paket beweist keine Unabhängigkeit.

Die Auswertung speichert ursprüngliche Top 3, richtigen Rang, Rang-1-/Top-3-Treffer,
Enthaltungen, falsche Zuordnungen, Gegenkandidaten, Quellenqualität und Dauer. Kandidatenrang
und tatsächlich erklärte Identifikation werden getrennt gezählt. Historische HT-IDs bleiben
Entwicklungsregressionen. Unabhängige Labels erfordern spätere belegte Auflösung,
Originalhash und Erklärung, dass der Fall nicht zur Entwicklung genutzt wurde. Es werden
keine Trefferquoten berechnet. Dateiexklusivität, Schreibschutz und Hash erkennen Änderungen;
das ist kein signiertes, gegen Administratoränderungen geschütztes WORM-Archiv.

## Optionsscheine und Abnahmestatus

Erst nach Aktienidentifikation und mit explizit konfigurierten offiziellen Emittentenhosts
werden begrenzte Produktsuchen zugelassen (`--product-issuers`, JSON Emittent → Host).
Nur ausdrücklich beschriftete WKN/ISIN, Basispreis, Laufzeit und Bezugsverhältnis werden
übernommen. Fehlende Felder bleiben leer. Die beworbene Original-Call-WKN wird ohne
konkrete Original-/Produktbelege nicht bestätigt; die aktuelle Implementierung gibt diese
Bestätigung grundsätzlich nicht automatisch frei. Keine Renditeextrapolation aus Hebeln.

Den tatsächlichen Prüfumfang und verbleibende Blocker dokumentieren der
[Abnahmebericht](hebeltrader-primary-acceptance.md) und sein JSON-Nachweis. Technische Tests
ersetzen weder einen realen unabhängigen Identifikationsnachweis noch eine gemessene
Trefferquote. Keine Orders, produktiven Migrationen oder Änderungen an Immich.
