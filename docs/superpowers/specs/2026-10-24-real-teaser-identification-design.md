# V2.3 Reale Teaser-Kandidatenidentifikation – Design

## Ziel und Grenzen

Der bestehende HEBELTRADER-Detektiv erhält drei explizite Betriebsarten: `fixture`,
`cached_research` und `live_research`. Kandidaten und Evidenz verwenden die gemeinsamen Modelle
aus `scanner.research`; weder der Research-Dienst noch der Detektiv erzeugen Kaufentscheidungen.
Beim API-Start findet kein Netzwerkzugriff statt. Live-Zugriffe erfordern eine ausdrückliche
Konfiguration, einen gültigen SEC-User-Agent und harte Request-Grenzen.

## Gewählter Ansatz

Ein versioniertes Research-Snapshot verbindet einen reproduzierbar und teaserunabhängig gewählten
Teil des SEC-Universums mit SEC-Submissions und begrenzt extrahierten Company-Facts. Das Snapshot
verweist auf unveränderliche Rohdaten im vorhandenen SHA-256-Cache und trägt seine eigene
kanonische Prüfsumme. `cached_research` liest ausschließlich diesen Stand. `live_research`
aktualisiert ihn erst während einer Analyse und nur innerhalb des konfigurierten Budgets.

Alternativen waren Abfragen je Teaser gegen einzelne, zuvor vermutete Firmen und eine eingebaute
Mini-Watchlist. Beide würden Lösungswissen in die Vorauswahl bringen. Ein Vollabruf aller
Company-Facts bei jeder Analyse ist wegen SEC-Last, Laufzeit und Request-Limits ebenfalls
ungeeignet. Der Snapshot macht diese Begrenzung messbar, statt Gesamtmarktabdeckung zu behaupten.

## Fakten und Zeitbezug

Ein Filing bleibt ein `document_event`. Konkrete Fakten werden separat gespeichert und enthalten
Kennzahl, Wert, Einheit, Vergleichswert und -zeitraum, Fundstelle, Quelle, Methode und
Verifikationsstatus. Nur streng passende SEC-XBRL-Perioden dürfen eine Veränderung belegen;
ansonsten lautet der Status `unknown`. Filing-Acceptance, Erstveröffentlichung, Abruf und
rekonstruierte Verfügbarkeit bleiben getrennt. Heute geladene Identitäten gelten ohne datierte
Quelle nicht automatisch historisch.

## Ranking und Ausgabe

Der bestehende Clue- und Rankingpfad wird erweitert. Belegte Übereinstimmungen, Widersprüche und
nicht prüfbare Hinweise werden getrennt ausgegeben. Ein Kandidat kann trotz offener Hinweise in
den Top 3 erscheinen, wird aber nur bei ausreichend belegter und eindeutig führender Evidenz als
plausibler Kandidat ausgewiesen. Es gibt keine Prozentwahrscheinlichkeiten. CLI und API verwenden
dieselbe Service-Factory und liefern dasselbe Report-Schema inklusive Modus, Coverage,
Providerstatus und Datenalter.

## Internationale Vorbereitung

GLEIF wird als zweiter echter Unternehmensdatenadapter implementiert: kostenlos, ohne Anmeldung,
CC0, mit historisierten LEI-Referenzdaten. GLEIF ist Identitätsevidenz und keine Nachrichtenquelle.
Die offiziellen Portale in Deutschland, Österreich und der Schweiz werden dokumentiert; eine
kostenlose dokumentierte Massen-API für historisch zeitgestempelte Emittentenmeldungen ist derzeit
nicht belegt und wird nicht simuliert.

## Sicherheit und Betrieb

Keine Datenbankmigration, kein Schreiben in PostgreSQL und keine Hintergrundabfrage. Snapshot-
und Rohdatenpfade sind lokale, explizit konfigurierte Verzeichnisse. Der reale E2E-Lauf bekommt
ein eigenes Request-Budget, protokolliert Kosten (`0 EUR`), Quellenstatus und Abdeckung und darf
bei unzureichender Evidenz nur `unresolved` zurückgeben.
