# V3.1 – tatsächlicher Abnahmebericht

Prüfdatum: 28.10.2026. **Fachliche Abnahme offen.** Der eigene V3.1-PR baut auf dem
noch ungemergten PR #28 (`212cc20`) auf. Keine Vermischung mit SEC-/Tiingo-PR #27.

## Technischer Stand und neue Funktionen

Vorhanden waren Text/PDF/OCR, Hinweismatrix, Top 3, fünf belegte Gegenkandidaten,
Falsifikation und eingefrorenes Einzelranking. Neu sind das dauerhaft nachvollziehbare
Falljournal, Autor/Ausgabe und Quellenprovenienz, fortgesetzte Quellen-/Inhaltsdeduplikation,
spätere Auflösungen/Korrekturen mit Fehleranalyse, bedingte Qualitätskennzahlen,
verifizierbare Zeitverträge, RSS-/Atom-Entdeckung und kompakte Fallberichte.

Das ursprüngliche falsche Top 1 wird durch eine richtige spätere Analyse nicht ersetzt.
Eine Auflösung ohne ursprünglichen Kandidaten kann den Fall lösen, wird aber nicht als
rechtzeitiger Treffer gezählt. Eine Nutzer-WKN wird nicht als Produktverifikation ausgegeben.
Zentralregister-Erweiterungen werden erst nach dem Freeze angehängt. Die 18 historischen
Einträge bleiben unverändert; der neue Fall erscheint separat unter einer TI-ID.

## Tatsächlich verwendete Quellen und reale Ergebnisse

1. Öffentlicher Herausgeberfeed `https://www.deraktionaer.de/aktionaer-news.rss`:
   HTTP 200 am 28.10.2026, zehn archivierte Einträge, Rohdatenhash im JSON-Nachweis.
   Zwei zunächst vermutete `/feeds/…xml`-Adressen lieferten 404; der echte Feed wurde
   danach durch öffentliche Recherche lokalisiert und direkt geprüft.
2. Bing-RSS-Suche: Robots-Regeln verhindern den Abruf. Diese Einschränkung wird nicht
   umgangen und bleibt im Quellenbericht sichtbar.
3. Ein echter anonymisierter RSS-Teaser „Doppelter Verzehnfacher: Beste Aktie,
   Top-Krytowährung“, Autor **Alfred Maydorn**, veröffentlicht laut Herausgeberfeed
   **28.10.2026, 11:28 UTC**, tatsächlich abgerufen **13:15:02 UTC**, wurde eingelesen.
   Das ist ein anderer Autor, **kein Rudolf-Wittmer-/HEBELTRADER-Fall**. Der öffentliche
   RSS-Auszug enthält nur allgemeine KI-/Krypto-Aussagen, keine genügend spezifischen
   Unternehmensereignisse. Der Lauf ist retrospektiv und unbewertet.
4. Die Recherche rief öffentliche Originalseiten des Herausgebers ab. Sechs Dokumente
   konnten extrahiert werden, null davon waren Primär-Unternehmensbelege. Zwei Seiten
   mit Paywall-Metadaten wurden nicht inhaltlich ausgewertet. Keine geschützten Zugänge.
5. Ergebnis: **null belegte Gegenkandidaten, keine Top 3, ungelöst**, keine Aktien- oder
   Derivatbestätigung. Fall `TI-282b503c1ac7bf3c491f`, unveränderte Erstprognose und
   Hashkette mit drei Ereignissen archiviert. Kein künstlicher Vergleich aus sechs
   zufälligen Aktien. Journal und Rankinghash wurden erneut validiert.
6. Automatischer HEBELTRADER-Feed-Einzellauf: null neue passende Teaser und null
   Benachrichtigungen. Das ist kein Nachweis vollständiger Teaserabdeckung.

SEC, Tiingo und andere kostenpflichtige Nachrichtenquellen wurden in diesem Lauf **nicht**
verwendet. Die vorhandenen Komponenten bleiben erhalten. Die manuelle Quellensuche nutzte
zusätzlich die vorhandene Tavily-Verbindung zur Feedadresse; sie ist kein neuer Runtimeanbieter.
Keine neuen Tarife, Zugangsdaten, KI-Endpunkte oder bezahlten Dienste eingerichtet.

## Regressionen und echte Blindtests

Alle **18 bekannten Fälle** sind inventarisiert. Die ADI-/CRM-Titelauszüge wurden ohne
Lösungen analysiert und bleiben ohne Originalbelege ungelöst. JPMs Original fehlt;
GS→JPM bleibt eine dokumentierte frühere Fehlprognose, kein erfundener neuer Test.
Allgemeine Regressionen prüfen spezifische Ereignisse vor Floskeln, Fremdfirmenzahlen,
Vergleichssätze, Quartale, Beteiligung versus Übernahme, fünf belegte Alternativen,
aktive Gegenrecherche, Quellenzeiten und Enthaltung. Bekannte Namen stehen nur in
getrennten Entwicklungslabels, nicht im Rankinginput.

Neue Regressionen prüfen außerdem Auflösung/Korrektur nach unveränderter Erstprognose,
Alias-Deduplikation, manipulierte Hashketten, ungültige Quellenzeiten, spätere
Archivabrufe mit Inhaltsbindung, Register erst nach Freeze, Vorregistrierung der
unabhängigen Kohorte, ungelöste Nenner sowie fehlende/leere API-Tokens.

**Unabhängig ausgewertete reale Blindtests: 0.** Der echte neue öffentliche Teaser ist
retrospektiv und hat keine belegte spätere Auflösung. Top-1-/Top-3-Trefferquoten bleiben
im tatsächlichen Qualitätsbericht leer. Die historische Gesprächsbilanz 10/7/1 wird nicht
als Modellbenchmark oder neue Erkennungsrate verwendet.

Vollständige lokale Testsuite, Ruff, Docker-Build und isolierter read-only/offline
CLI-Lauf: siehe [maschinenlesbarer Nachweis](teaser-v31-acceptance.json). PostgreSQL-Tests
benötigen eine isolierte Testdatenbank; GitHub-CI richtet sie selbst ein. Die lokale
Starlette-/AnyIO-DeprecationWarning betrifft eine bestehende Abhängigkeit.

## Verbleibende Blocker und nächster Schritt

- Noch kein unbekannter HEBELTRADER-Originalteaser mit ausreichend spezifischen Hinweisen,
  mindestens fünf tatsächlich belegten Alternativen und späterer getrennter Auflösung.
- Der Feed liefert nur aktuelle Einträge. Globale Suchabdeckung und Unternehmenszuordnung
  sind unvollständig; fehlende explizite Identitätsmetadaten begrenzen Kandidatengenerierung.
- Datierte Primärbelege und inhaltsgebundene historische Archivversionen fehlen für den
  realen Versuch. Eine frühe Publikation allein genügt nicht für bestätigte alte Evidenz.
- Nutzerauflösungen und importierte Archivprovenienz benötigen Betreiberprüfung. Hashketten
  schützen nicht vor einem Administrator, der die gesamte Kette neu schreibt.
- Zentrale MD-Synchronisierung aus dem API-/Containerbetrieb benötigt einen ausdrücklich
  konfigurierten, beschreibbaren Registerpfad oder den separaten CLI-Export. Lokales
  Journal und lokale Registererweiterung bleiben erhalten. Externe Zustellung fehlt.

**Empfehlung:** Draft technisch prüfen; keine fachliche Produktionsfreigabe und kein Merge
auf Basis von Testzahlen. Als nächsten Schritt einen neuen rechtmäßig zugänglichen,
vollständigen HEBELTRADER-Teaser vorregistrieren, Quellen gezielt zu seinen konkreten
Ereignissen sammeln und nach Einfrieren der Erstprognose eine spätere Originalauflösung
belegen. Dazu ist derzeit kein neues kostenpflichtiges Abo erforderlich. Für automatische
API-Recherche ein nicht leeres lokales Token und geprüfte IR-Hostzuordnungen konfigurieren.
Kein Codex-Zugriff auf Hetzner wurde benutzt oder behauptet. Kein produktives Deployment,
keine Migration, kein Merge, keine Änderungen an Immich und keine Wertpapierorders.
