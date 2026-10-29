# Öffentliche HEBELTRADER-Ausgaben automatisch erfassen

Kleine Ergänzung zu PR #29; kein neues Deployment, keine Orders, keine Abos.

Bestand: `TeaserMonitor` sucht über RSS/Bing, journalisiert über `run_case`, dedupliziert
und erzeugt lokale Meldungen. Lücke: Die öffentliche Produktübersicht wird nicht gelesen;
Produktüberschriften heißen nur „HEBELTRADER 200/26“, und die generische Textauslese mischt
Teaser mit Kaufbuttons und anderen Ausgaben. Ein Datum ohne Uhrzeit darf nicht zu
angeblich genauer historischer Verfügbarkeit werden.

1. Neuer kleiner `publisher_catalog.py`-Parser: nur erlaubte öffentliche Börsenmedien-Produktlinks;
   Teaserbereich, Ausgabe, Autor und Erscheinungsdatum gezielt lesen; Navigation,
   Kaufbereich, andere Ausgaben und PDF-/Downloadlinks nicht als Teaser übernehmen.
   Unbekanntes Layout bleibt Fehler, kein Ganzseiten-Fallback.
2. Vorhandenen Monitor um begrenzte Katalogentdeckung ergänzen. Gleiches HTTP-Archiv,
   Robots-/Budgetregeln, dieselbe Deduplikation, Journal-Engine und Benachrichtigungsgates.
   Nur lokal erstmals gefundene Fälle zählen als neu, nicht angeblich neu veröffentlicht.
3. Vorhandene CLI `watch --once` standardmäßig mit Herausgeberkatalog, begrenzten Produkten
   und optional `--no-catalog` für den bisherigen RSS-Pfad. Kalenderdatum separat speichern,
   Uhrzeit unbekannt lassen. Keine Lösungen oder bezahlten PDFs lesen.
4. Test-first: Fremdlinks, Layoutfehler, Seitenleistenkontamination, date-only, Wiederholung
   und Fehlerfortsetzung. Danach echter Einzellauf plus Wiederholung auf denselben Daten,
   vollständige Suite, Ruff und nachvollziehbarer Quellen-/Ergebnisbericht in PR #29.

Nicht Gegenstand: neue Optionsscheinlogik oder Behauptung bereits vollautomatischer
Aktienidentifikation. Ein gefundener Teaser darf mangels Primärbelegen ungelöst bleiben.
