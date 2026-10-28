# V2.7 – tatsächlicher Abnahmebericht, 28.10.2026

**Fachliche Live-Abnahme nicht bestanden.** SEC-Erfassung funktioniert mit realen
Daten; die geforderte tatsächliche Marktreaktion ist ohne Marktdatenzugang nicht
überprüfbar. Kein Kaufalarm und keine Produktionsfreigabe.

## Ist-Stand und PR-Bereinigung

Begonnen auf main `35f89bc` mit PRs #21–24. Auf zusätzlichen Auftrag und ausdrückliche
Merge-Freigabe des Inhabers wurden #16 und #25 geprüft und gemergt; #26 wurde wegen
unbelegter Produktdaten/historischer Verfügbarkeit ohne Merge geschlossen. Issues
#4/#7 sind geschlossen. V2.7 basiert abschließend auf main `259b684`. V2.7 selbst
wird ausschließlich als überprüfbarer PR vorgelegt. Kein Hetzner-Deployment.

## Realer Lauf

Umgebung: isolierter Entwicklungscheckout, nicht Hetzner.
SEC-User-Agent für den kontrollierten Versuch aus der vorhandenen Git-Autorenidentität;
keine erfundene Kontaktadresse. Tiingo-Token nicht vorhanden.

Maschinenlesbarer Nachweis: [live-v27-acceptance.json](live-v27-acceptance.json).
Run-ID `f4c33cc52a1f46cd838f98f5e568640b`, Ende
`2026-10-28T07:02:07.535443+00:00`.

- 100 Emittenten anhand frischem SEC-Universum geprüft.
- 27 neue aktuelle SEC-Meldungen erstmals im Journal erfasst.
- 10 Meldungen einer Detailprüfung/Entscheidung zugeführt, 17 budgetbedingt vertagt.
- 104 tatsächlich durchgeführte Quellenabrufe, HTTP-Status im Nachweis.
- Drei Originaldokumente archiviert: INTA 10-Q, ESS 8-K, INTA 8-K.
- Sieben Form-4-Dokumentpfade mit XSL-Unterverzeichnis wurden vom konservativen
  Pfadfilter zurückgewiesen; kein Insiderkauf daraus behauptet.
- Zehn Entscheidungen `NICHT VERFÜGBAR` wegen fehlender Marktdaten.
- Null überprüfte Kursreaktionen, null Kaufalarme, keine Rendite-/Trefferquote.

Beispiel ESS (Essex Property Trust): 8-K, Items `2.02,9.01`, SEC-Publikation
`2026-10-27T20:34:17+00:00`, Originaldokument:
https://www.sec.gov/Archives/edgar/data/920522/000114036126040903/ef20084268_8k.htm .
Der Ergebnisbericht ist ein realer Katalysator-Kandidat, seine positive Überraschung
wurde nicht fundamental bestätigt. Der SEC-Zeitpunkt ist nicht als frühester
IR-Veröffentlichungszeitpunkt bewiesen. INTA meldete ebenfalls Ergebnisse am
27.10.2026. Originalabrufzeiten und SHA256 stehen im JSON-Nachweis.

Journal nach diesen Läufen: 383 verkettete Einträge; Endhash
`fea5a183db7259112a9bf2f0277e224d77b95690d0305e541e149e88dd2dba15`.
Rohdaten, vollständiger JSON-Journalexport und Datenbank sind lokal im Bundle
`reports/live-v27-evidence.tar.gz` gespeichert, SHA256
`484603ac002c1663e00cb7aff787b28beba4bfaa1760565352e13451a25e3723`.
Das Bundle liegt bewusst außerhalb von Git; Kurs-/Quellenrohdaten werden nicht als
synthetische Testdaten umetikettiert. Der kompakte, überprüfbare Auszug liegt im PR.

## Technische Prüfung

- Sicherheitstests einschließlich kompletter Pipeline mit HTTP-Testtransport,
  Deduplizierung, Wiederbewertung, Wiederanlauf, API, Quoten und Deadline-Grenzen.
  Diese Adaptertests sind synthetische Regressionen, **keine Live-Abnahme**.
- Vollständige Testsuite (`.venv/bin/python -m pytest -q`): **700 bestanden,
  8 übersprungen**, eine DeprecationWarning aus Starlette/AnyIO. Ruff und
  Formatprüfung für scanner/tests sowie Git-Diff-Prüfung bestanden.
  Ein vorheriger Aufruf über das pytest-Skript ohne Projektpfad scheiterte bei
  der Importsammlung des übernommenen V2.0-Tests (`tests` nicht im Pythonpfad);
  der reguläre Modulaufruf oben behebt den Aufrufpfad, nicht den Produktcode.
- Docker-Image in dieser Umgebung gebaut; isolierter Containerlauf ohne Netzwerk
  protokolliert fehlenden SEC-User-Agent korrekt mit Exitcode 2.
- Separates Compose-Projekt validiert. Kein Serverzugriff/produktiver Start.
- Unabhängiges Review fand Quota-Reservierung bei Cache-Hits, ungünstige
  Universum-Budgets und Deadline-/Abrufprotokoll-Lücken; mit Regressionen korrigiert.

## Exakt verbleibende Voraussetzungen

1. Auf dem späteren Ausführungssystem `SEC_USER_AGENT` mit tatsächlichem Kontakt
   konfigurieren. Für die hier gezeigte öffentliche SEC-Abfrage war kein API-Key nötig.
2. `TIINGO_API_TOKEN` sicher bereitstellen und vorhandene kostenlose Nutzungsrechte
   prüfen; dann explizit `--authorize-tiingo` setzen. Ein anschließender realer Lauf
   muss mindestens ein Vorher-/Nachher-EOD-Paar zum Ereignis nachweisen. Für Meldungen
   des Vortags kann die vorsichtige Tagesabgrenzung zunächst noch kein Nachher liefern.
3. Für ausführbare Kauf-Limits zusätzlich lizenzierte aktuelle Quotes, verifizierte
   Börsenkalender und ISIN-Zuordnung, belegte fundamentale Primärbestätigung,
   Kosten/Spread und sinnvolle Ziel-/Stoppmarken. Keine dieser Quellen ist aktuell
   eingerichtet oder als flatex-Handelbarkeitsnachweis vorhanden.
4. Für administrative Unveränderbarkeit externen WORM-/Object-Lock-Speicher oder
   unabhängig gesicherte zeitgestempelte Journalhashes einrichten. SQLite-Trigger
   und Hashkette allein sind kein administrativer Löschschutz.
5. Hetzner: Verantwortlicher prüft Compose, legt ein ausschließlich diesem Scanner
   gehörendes Datenverzeichnis mit passender UID/GID und Secret-Datei (0600) an,
   baut Image und startet zunächst den dokumentierten Einzellauf. Erst nach Review
   erfolgt separat die Freigabe für Dauerbetrieb/API. Kein SSH-Zugang wurde benötigt
   oder verwendet, keine fremden Container/Volumes wurden berührt.

DACH-, Community-, Investment- und Derivat-Erweiterungen bleiben gemäß Reihenfolge
des Auftrags bis zur erfolgreichen End-to-End-Live-Abnahme offen. Steyr Motors ist
in dieser US-Stichprobe nicht abgedeckt. Historische Erfolgsklassen, automatische
Fill-/Folgeauswertung, Branchen-/Smallcap-Quote und qualifizierte Benachrichtigungen
sind noch nicht umgesetzt. Laufzeitgrenze ist kooperativ mit höchstens zehn Sekunden
Timeout je laufender HTTP-Phase; sie ist kein harter Prozess-Kill während Netzwerk-I/O.
