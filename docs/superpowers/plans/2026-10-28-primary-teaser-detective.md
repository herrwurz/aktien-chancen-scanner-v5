# HEBELTRADER als primäre Funktion – kleiner Entwicklungsplan

Ausgangsbasis main e504ad9; eigener Branch/PR, keine Vermischung mit PR #27.
Der SEC-Frühscanner bleibt dort nachgeordnet erhalten. Keine Deployments/Orders/Abos.

## Inventur
Bestehend: Text/PDF/OCR, AtomicClue, Stage-A-Quellen, Stage-B-Matrix, Top-3,
getrennte Blindtest-Auswertung und Detektivseite. Lücken: weltweite dynamische
Suche ohne EU-/100er-Seed-Bindung, verpflichtende Gegenkandidaten/Falsifikation,
zu frühe Derivatzuordnung, Hintergrund-Teaserdeduplizierung und Einbindung der 18 Fälle.
Die Fallhistorie enthält fehlende Originaltexte/Zeiten und darf keine Blindtest-Eingabe sein.

## Umsetzung
1. Öffentliche, budgetierte Recherche mit archivierten Originalseiten und verifizierter
   Zeitmetadatenbehandlung; Suchtreffer dienen ausschließlich der Entdeckung.
2. Vorhandene Eingabeextraktion und Evidenzprüfung wiederverwenden. Gleiche Matrix für
   mindestens sechs plausible Unternehmen (Spitzenkandidat plus fünf Alternativen),
   konkrete Ereignisse und Zahlen vor Branchenfloskeln. Harte Gegenbelege dominieren.
   Aktive Gegensuche zum Führenden und stärksten Konkurrenten vor Einfrieren.
3. Top-3 plus vollständiger Vergleich, Quellen/Gegenargumente, unkalibrierter Score.
   Fehlende Primärbestätigung, dünner Vergleich oder fehlende Datierung => nicht identifiziert.
   Keine Optionsscheinbestätigung ohne datierte Produktbelege nach Aktienidentifikation.
4. Historie offline auf alle18 inventarisieren; Rankings unveränderbar einfrieren,
   erst danach Labels lesen. Williams bleibt unbewertet; Regressionen sind keine neue Trefferquote.
5. Primäre Startseite/API/CLI; optionaler öffentlicher Teaser-Poller mit dedupliziertem
   lokalem Benachrichtigungsausgang für neue/wesentlich verbesserte Analysen. Kein Dienststart.
6. Regressionen, vollständige Suite, tatsächlicher Quellen-Smoke-Test und eigener PR.

## Entscheidungen und Grenzen
Kein neues Daten-/KI-Abo. Deterministische Fakten-/Wortlautprüfung mit offengelegten
Unbekannten statt generiertem Wissen. Öffentliche RSS-Suche ist global ausgerichtet,
aber keine vollständige Weltmarkt-Abdeckung. Öffentliche Teaserseiten werden geprüft;
Login und Bezahlinhalte bleiben ausgeschlossen. Fehlende Originalteaser werden nicht erfunden.
Die Regeln aus der Historie werden nur als allgemeine Anti-Anker-Regeln umgesetzt,
nie als Teaser→Aktie-Zuordnung im Laufzeitcode. Ehemals gelöste Fälle sind Entwicklungstests.
