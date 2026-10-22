# HEBELTRADER Backtesting V1

Userauftrag: PR #5 gemäß Issue #4 vervollständigen, ohne Deployment.
Bestehende Parser-, Import-, Review- und Datenbankarchitektur bleibt erhalten.

## Entscheidungen

Der vorhandene Offline-CLI wird zu einem ausschließlich lesenden Analyseweg
vervollständigt. Kein neuer persistierender Outcome-Weg und keine Migration.
Je gespeicherter Empfehlung entsteht ein nachvollziehbares Ergebnis, auch wenn
Preis-, Regel- oder Verfügbarkeitsbelege fehlen. Archivordner und Dateinamen
werden weder abgefragt noch als Erfolg oder Feature verwendet.

Die CSV-Provider-Schnittstelle validiert explizite Instrumentzuordnung, Börse,
Zeitzone, Währung, unveränderte Preise, Handelskalender, Corporate Actions und
Abdeckung. Ohne belastbare Quelle gibt es `data_unavailable` statt Ersatzwerte.
Live-Quellen werden dokumentiert bewertet; kein kostenpflichtiger Dienst.

Der Simulator verwendet nur vollständige Bars nach belegter Verfügbarkeit und
bis zum Auswertungsstichtag. Entry am ersten belegten Session-Open ist ein
explizites Modell, keine ausgeführte Order. Ein modellierter 50%-Teilverkauf und
Folgestopp benötigen dokumentbezogene Regeln. Zeitablauf nur mit expliziter
Kalender-/Handelstagesregel. Fehlende oder unklare Regeln ergeben unknown.
Intrabar-Reihenfolgen werden nicht erfunden. Derivate bleiben unabhängig davon
`derivative_unverified`; Laufzeit ist kein Aktien-Ausstieg.

Regeln werden pro Dokument-SHA und Empfehlungsordinal in einem optionalen
JSON-Sidecar geliefert. Erforderlich: Seite, wortgetreues Quellenzitat,
Prüfer und timezone-aware Prüfdatum. Das Zitat muss im gespeicherten Originaltext
stehen; ein Sidecar ist eine nachvollziehbare manuelle Regelinterpretation,
keine automatische Beweisführung für Semantik. Keine pauschale Textheuristik.

Approved-Review, ausgewählte Ausgabe und historische Verfügbarkeit entscheiden
über die Kennzeichnung als verifizierter Quellenbestand. Pending bleibt
Research-only. Ohne belegte Availability wird kein Pfad simuliert. Alle Modelle
bleiben von realisierten Renditen getrennt; keine Erfolgsquote aus indikativem
OHLC. Quellen-, Regel- und Eingabehashes, Version, Retrieval-Zeit, Lücken,
Ereignispfad und Beobachtungsfenster ermöglichen Audit und Wiederholung.

JSON-/CSV-Exporte entstehen nur an expliziten neuen Pfaden mit Modus 0600.
Keine Produktionsveränderungen, Hetzner-Kommandos, Trades oder Scheduler.

## Verifikation

Deterministische Fixtures: Gaps, Intrabar-Ambiguität, 50%-Teilverkauf,
dokumentierte Zeitregeln, Splits/Dividenden, Währung, Feiertage, fehlende Bars,
Open End, Delisting, Verfügbarkeit und Stichtag. 118 Empfehlungen ohne Daten
müssen 118 nachvollziehbare unknown-Ergebnisse ergeben. Vollständige bestehende
Suite einschließlich PostgreSQL, Docker und GitHub-CI vor Fertigmeldung.
