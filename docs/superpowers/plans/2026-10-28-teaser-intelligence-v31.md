# V3.1 – Teaser Intelligence Scanner: Umsetzungsplan und Gap-Analyse

Ausgangsbasis: PR #28, Commit 212cc20; eigener darauf aufbauender PR, kein Merge/Deployment.
Spezifikation: verbindlicher Nutzerauftrag V3.1 vom 28.10.2026 und
`docs/hebeltrader-identification-rules.md` (alle 18 Einträge geprüft).

## Bestandsaufnahme

| Anforderung | Vorhanden | Verbleibende Lücke |
|---|---|---|
| Text, URL, PDF, OCR | V3/PR28 Eingabeextraktion | Autor/Ausgabe, stabile Fall-ID, Fallstatus |
| Weltweite Recherche | PR28 budgetierte öffentliche Suche, keine 100er-Bindung | Bing-RSS gesperrt; zusätzliche konfigurierbare öffentliche Feeds nötig |
| Einheitliche Matrix/Top3/Falsifikation | PR28 mit fünf belegten Gegenkandidaten | Rankings begründen; in Fallhistorie wiederfinden |
| Historische Evidenz | Quellen-Publikation, Abruf, Blindpaketfilter | Publikation wird fälschlich als Verfügbarkeit übernommen |
| Unveränderte Erstprognose | PR28 eingefrorenes Ranking mit SHA256 | Dauerhaftes Falljournal, spätere Auflösung/Korrektur und Fehleranalyse |
| 18 historische Fälle | getrenntes Inventar; 17 berichtet aufgelöst, Williams offen | Entwicklungsregressionen, keine Originale/echten Blindtests erfinden |
| Qualitätsmessung | Einzeldatei-Auswerter, Raten bewusst leer | Kohorte aus Erstprognosen, Nenner/Enthaltungen, Zeit und Quellenabdeckung |
| Derivate | nach Aktienidentifikation, nur offizielle Hosts | Nutzerbestätigte Original-WKN getrennt von Produktverifikation erfassen |
| SEC/Tiingo | bestehende Adapter/PR27 separat | nicht duplizieren oder globale Abdeckung behaupten |

## Kleine Umsetzung mit vorhandenen Komponenten

1. **Zeitvertrag** (`temporal.py`, `investigation.py`, `public_web.py`): Ereigniszeit,
   Publikation, belegte Verfügbarkeit und tatsächlichen Abruf getrennt führen. Unbelegte
   historische Verfügbarkeit ist unsicher und bestätigt keine damalige Evidenz.
   Tests zuerst: spätere Verfügbarkeit, fehlender Nachweis, spätere Revision, Zeitzone.
2. **Falljournal** (`case_journal.py`): isolierte append-only JSONL-Hashkette mit Lock/fsync;
   Quellen-/Inhaltsdeduplikation, Erstprognose, weitere Analysen und spätere Auflösungen
   ohne Überschreiben. Zentralregister nur im getrennten Nachbereitungsschritt ergänzen;
   Ranking liest weder Register noch Lösungen. Tests: Dubletten, Korrekturen, Manipulation,
   erste Top3 unverändert, Bestätigung einer Nutzer-WKN ist keine Produktprüfung.
3. **Benutzung** (`investigate_cli.py`, API und vorhandene Webansicht): Autor/Ausgabe,
   Fallstatus, Auflösung mit Quelle/Fehleranalyse; kompakter Markdownbericht; manuelle
   Registerfortschreibung ohne produktive Datenbankmigration. Geschützte Schreib-API.
4. **Öffentliche Recherche** (`public_web.py`): konfigurierbare öffentliche RSS/Atom-Feeds
   als zusätzlicher Entdeckungskanal unter denselben Robots-/Budget-/Archivregeln.
   Suchtreffer bleiben Hinweise; Originalseite ist Pflicht. Keine privaten/Bezahlinhalte.
5. **Qualität und Nachweis**: Erstprognosen getrennt nach Entwicklung/retrospektiv/unabhängig
   auswerten. Top1/Top3 mit explizitem Nenner und Enthaltungen, falsche sichere Zuordnungen,
   Recherchezeit und Quellenabdeckung; keine Rate bei fehlender belegter unabhängiger Kohorte.
   Die drei dokumentierten Fehlversuche bleiben unverändert; fehlende Originale ergeben
   blocked, keine erfundenen historischen Tests. Öffentlichen Quellenlauf real archivieren.
6. Vollständige Suite, Ruff, Docker, tatsächlicher Bericht, eigener Draft-PR.

## Grenzen und Review-Fokus

Keine neuen Abos/KI-Kosten/Orders. Kein Serverlauf ohne Zugang. Kein Auto-Merge.
Blindscanner bekommt keine Fallregister-/Lösungsdateien. Der spätere Auswerter und
Registerexport sind getrennte Schritte. Hashketten sind kein extern signiertes WORM.
Besonders prüfen: gleiche URL mit neuer Ausgabe, gleiche Inhalte unter anderer URL,
Korrekturen nach Auflösung, leere Kandidaten, unklare Zeitmetadaten und unvollständige
Quellen. Die funktionierende Recherche hängt weiterhin von tatsächlich erreichbaren,
rechtlich nutzbaren Quellen und expliziten Unternehmensbelegen ab.
