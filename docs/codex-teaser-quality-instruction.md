# Codex-Anweisung: Teaser-Identifikation mit belegbarer Qualität

Stand: 28.10.2026. Auftrag ist die gezielte Weiterentwicklung des bestehenden Systems.
Dieses Dokument ist ein Umsetzungsauftrag, kein Nachweis bereits verbesserter Erkennungsqualität.

## Verifizierter Ausgangspunkt

Repository: https://github.com/herrwurz/aktien-chancen-scanner-v5

Am 28.10.2026 über GitHub gelesene PR-Metadaten:
- #27: offen, Draft, main → feat/live-fruehscanner-v27; Head fca26881b784a801c33866245216728c53ba2669. Separater SEC-Live-Pilot; fachliche Abnahme offen.
- #28: offen, Draft, main → feat/hebeltrader-primary-detector; Head 212cc202341bc29e07c90dcefd4222a695a0aaf2. Primärworkflow, Webrecherche, Gegenkandidaten, Falsifikation und Freeze vorhanden.
- #29: offen, Draft, feat/hebeltrader-primary-detector → feat/teaser-intelligence-v31; Head 7483e28a66389398609590f52b96f24affc7b0ad. Katalogeingang, Falljournal, Auflösung, zeitbezogene Evidenz und Kohortentrennung vorhanden.

PR-Beschreibungen berichten 700/725/751 bestandene Tests; diese Zahlen wurden bei dieser Dokumentationsprüfung nicht selbst erneut ausgeführt. Laut Katalognachweis wurden drei öffentliche HEBELTRADER-Fälle eingelesen, aber keiner automatisch ausreichend identifiziert. SLB/VY95PV wurde assistentengestützt getroffen und später per Nutzer-PDF bestätigt: kein autonomer Scanner-Erfolg. Null unabhängig ausgewertete reale Blindtests.

Zuerst erneut main, alle offenen PRs, Heads, Reviews, CI, AGENTS.md und Abhängigkeiten prüfen. Bei verschobenen Heads den Unterschied dokumentieren und diesen Auftrag anpassen. Auf geprüftem #29-Stand in isoliertem Branch/Worktree arbeiten; keine PRs automatisch mergen. #27 bleibt getrennt. Falls #28/#29 inzwischen gemergt sind, vom aktuellen main ausgehen.

## Ziel und Grenzen

HEBELTRADER/Rudolf-Wittmer-Teaser sind Hauptfunktion; der allgemeine Markt-/SEC-Scanner liefert ergänzende Identitäten, Ereignisse und Kurskontext. Keine weitere Startseiten-Neuentwicklung, wenn #28 dies schon erfüllt.

Wiederverwenden:
- scanner/hebeltrader/detective/service.py: Text/PDF/OCR-Eingang.
- investigation.py, verification.py: Hinweisextraktion, Kandidatenmatrix und Ranking.
- public_web.py, publisher_catalog.py, monitor.py: begrenzte Quellenabrufe, Katalog, Deduplikation.
- temporal.py: Publikations-, Ereignis-, Abruf-, Revisions- und Verfügbarkeitszeiten.
- history.py, case_journal.py, resolution.py, workflow.py: Freeze, Erstprognose, Journal, spätere Auflösung und Evaluation.
- product_research.py: nachgelagerte, getrennte Produktprüfung.
- bestehende Benchmark-Skripte und Tests: vor Erweiterung lesen und gemeinsame Logik nutzen.

Keine neuen parallelen Journale, Parser oder Evaluatoren ohne belegte Notwendigkeit. Python 3.12, FastAPI, Pydantic, httpx und pytest/Ruff beibehalten. Vorhandene Daten und Erstversuche erhalten. Keine produktiven Migrationen, Dienste, Hetzner-/Immich-/Volume-Änderungen oder Orders. Monatlich höchstens 20 EUR zusätzliche Daten-/KI-Kosten; Standard ohne neue laufende Kosten. Keine Abos oder kostenpflichtigen Provider aktivieren. Chat-Connectoren sind keine automatisch verfügbaren Server-APIs.

## Aufgabe 1: Recherche statt Metadatenzufall

Betroffene Dateien: public_web.py, investigation.py; gezielte Erweiterung der vorhandenen Quelladapter. Tests: test_detective_public_web.py und test_primary_investigation.py.

- Vollständigen Originalteaser einschließlich Überschrift und Kontext erfassen. Kürzung, OCR-Lücken und unbekannte Layouts sichtbar machen; keine vollständige Analyse behaupten, wenn relevante Teile fehlen.
- Atomare Hinweise mit Originalstelle, Kategorie, Unternehmen/Subjekt, Relation, Wert, Einheit, Berichtsperiode und zeitlichem Bezug ausgeben. Auch qualitative Quartals-, Branchen-, Produkt- und Ereignishinweise berücksichtigen. Werberenditen getrennt halten.
- Suchqueries aus konkreten Ereigniskombinationen und einzelnen Hinweisen deutsch/englisch erzeugen; kein festes US-/Branchenuniversum und keine gelösten Fallnamen als Suchseed.
- Aktuell nutzt die Suche Bing-RSS plus konfigurierte Feeds. Ein allgemeiner Herausgeberfeed ersetzt keine weltweite Unternehmensrecherche. Zuerst mit zulässigen Quellen reale Suchabdeckung nachweisen. Identitätsauflösung aus Inhalt und geprüften IR-/Registerbelegen ergänzen: fehlendes company_name/ticker-Metadatum darf eine eindeutig belegte börsennotierte Firma nicht unsichtbar machen. Tochterunternehmen, Transaktionsziel und berichtendes Unternehmen unterscheiden.
- Suchtreffer sind Entdeckung, keine Evidenz. Original-Unternehmensquelle/Regulator abrufen und mit Rohdatenhash archivieren. IR-Domain allein beweist keine konkrete Aussage. Übernahme, Beteiligung, Kooperation, Ankündigung und Vollzug getrennt bestätigen.
- Requests, Laufzeit, Bytes und Kosten pro Lauf begrenzen; Recherchebudget auch für Gegenkandidaten und Falsifikation reservieren. Robots, 403/429, Zugangssperren und Quellenlücken respektieren und ausweisen.
- Vor Score-Tuning Fehler getrennt messen: Kandidat nicht entdeckt, Identität nicht aufgelöst, Beleg nicht extrahiert, zeitlich nicht zulässig, falsch gerankt.

Regressionen zuerst: Firma ohne Metadaten mit belegter Identität; fremde Firma/Tochter in IR-Text; unterschiedliche Quartale/Einheiten; Erwerb versus Minderheitsbeteiligung; vollständiger Teaser mit spät stehendem entscheidendem Hinweis; Suchausfall und Budgetende führen zu sichtbarer Lücke.

## Aufgabe 2: Fünf tatsächlich geprüfte Gegenkandidaten

Betroffene Dateien: investigation.py, verification.py; bei Bedarf kleines eigenes Vergleichsmodul statt weiterer monolithischer Erweiterung. Tests in test_primary_investigation.py ergänzen.

Aktuell basiert comparison_evidence_available auf teaser_term_overlap. Das belegt keine ernsthafte Gegenkandidatenprüfung. Ersetze diese Zählgrundlage durch einen nachvollziehbaren Prüfvertrag:
- Mindestens sechs unterschiedliche plausible börsennotierte Unternehmen insgesamt: Favorit plus mindestens fünf Gegenkandidaten. Keine Mehrfachzählung durch Alias, Börsenplatz oder duplizierte Meldung.
- Für jeden: konkrete Plausibilitätsbegründung, dieselben Kernhinweise als bestätigt/widersprochen/unbekannt, passende Quellen, aktive Suchversuche und Ausschluss-/Offenheitsgrund. Ein bloßes KI-Schlagwort zählt nicht als geprüfte Alternative.
- Top 3 ausführlich mit identischer Matrix, Primärbelegen, Datumsbezug, Gegenargumenten und Erklärung der Rangfolge vergleichen. Fehlender Beleg bleibt unbekannt; fehlender Suchtreffer ist kein Gegenbeweis.
- Vor Festlegung gezielt stärkste Alternative und mögliche Gegenbeweise zum Favoriten prüfen. Query-Ausführung allein bedeutet nicht erfolgreich abgeschlossene Falsifikation. Ergebnisse und Lücken protokollieren.
- Wechselt der Favorit, auch ihn prüfen, bis stabil oder Budgetende; bei offenem Prüfschritt keine bestätigte Identifikation.
- Harte Widersprüche nicht durch zahlreiche allgemeine Treffer überstimmen. Bestätigte spezifische Primärereignisse vor Marketing, Wachstum und Charts. Keine neue Prozent-Konfidenz.
- Sind fünf plausible Alternativen nicht belegbar: konkrete Begründung und Hypothesen/Enthaltung ausgeben; keine Füllkandidaten und keine Lockerung zur Verbesserung der Quote.

Regressionen zuerst: sechs generische KI-Seiten reichen nicht; fünf wirklich geprüfte Alternativen bestehen; Alias-/Syndizierungsduplikate zählen einmal; Widerspruch schlägt generische Treffer; Führungswechsel fordert neue Falsifikation; Quellen-/Budgetausfall verhindert Erfolgsstatus. Keine Gewinnernamen im Produktionscode.

## Aufgabe 3: Historische Blindprüfung fachlich und technisch ermöglichen

Betroffene Dateien: investigation.py, temporal.py, history.py, workflow.py und bestehende Benchmark-Einstiegspunkte. Tests: bestehende History-/Temporal-/Workflow-Tests sowie gezielte neue Benchmark-Regressionen.

Aktueller Zielkonflikt: historical_blind verlangt archivierte Offline-Dokumente, aber identified verlangt not offline; offline erzeugt zudem active_falsification_not_performed. Korrigiere den Vertrag, ohne einfach diese Schutzbedingungen zu entfernen:
- Offline darf identifizieren, wenn ein vollständiges, zeitlich zulässiges Recherchepaket einschließlich dokumentierter Gegenkandidaten- und Falsifikationsbelege vorliegt. Sonst Hypothese/Enthaltung. Ein nach Lösungen kuratiertes Paket ist nur Regression, kein unabhängiger Test.
- Recherchequalität und Rankingqualität getrennt evaluieren. Vorbefüllte Kandidatenpakete testen das Ranking; für die gesamte Pipeline muss auch die Entdeckung unbekannter Firmen labelblind erfolgen.
- Ereigniszeit, Publikationszeit, Inhaltsversion, historische Verfügbarkeit und heutiger Abruf bleiben getrennt. Ein heutiger Abruf einer alten Seite beweist die damalige Fassung nicht. Date-only bleibt date-only; konservative Ausschlüsse und Annahmen dokumentieren.
- Scannerprozess erhält ausschließlich neutrale Inputs, Index/Quellen und Konfiguration. Kein Fallregister, keine Lösungs-PDFs, WKN-Zuordnungen, Lösungen in Pfaden/Dateinamen oder Labels mounten. Label-Leseversuch technisch verhindern und testen.
- Vor Evaluation Ranking, Input-/Quellenmanifest, Code-Commit, Konfiguration, Modell-/Promptversion (falls eingesetzt), Recherchebudget und Laufzeiten einfrieren. Hashprüfung vor Lesen der separat gehaltenen Lösungen.
- Die bekannten 18 Fälle bleiben development_regression. Historisch unbekannte, aber heute rekonstruierte Fälle nur bei dokumentierter Unberührtheit als unabhängige historische Kohorte behandeln; Modellvorwissen und heutige Suchergebnisse als Kontaminationsrisiko ausweisen. Sonst retrospective.
- Unabhängigen Holdout vor Ausführung registrieren, Entwicklungsentscheidungen nicht daran optimieren, Originalauflösungen separat prüfen. Neue vor Auflösung eingefrorene Fälle als prospective_blind ergänzen.
- Vollständige Originale und Lösungen nicht erfinden. Fehlendes Material blockiert die reale Abnahme, nicht die ehrliche Dokumentation.

Regressionen: vollständiges Offline-Paket kann dieselbe Entscheidung wie äquivalente zulässige Live-Evidenz tragen; fehlende Falsifikation bleibt Enthaltung; später revidierter Inhalt ausgeschlossen; date-only-Beleg nicht mit erfundener Uhrzeit; Registerzugriff unmöglich; manipuliertes Manifest abgewiesen; bekannter Entwicklungsfall auch mit neuer ID nicht unabhängig.

## Aufgabe 4: Verbesserung belegen und Wissen erhalten

Betroffene Dateien: history.py/workflow.py nur soweit nötig, docs/hebeltrader-identification-rules.md, vorhandene Abnahmeberichte und gezielte Tests.

- Unveränderte alte Baseline (#29-Head oben) und neue Version auf identischer, vorab festgelegter Kohorte, gleichen zulässigen Quellenständen und vergleichbaren Budgets ausführen. Alte Ergebnisse separat einfrieren; neue Läufe überschreiben keine Erstversuche.
- Baseline und neue Version jeweils ohne Labelzugriff starten. Für End-to-End-Recherche Herkunft und Aufbau des neutralen historischen Quellenbestands dokumentieren; ein nur für den Gewinner angelegtes Paket ist unzulässig.
- Ausweisen: registriert, ausgeführt, fehlgeschlagen, ausgeschlossen mit Grund, ungelöst, auswertbar, Top-1-/Top-3-Rangtreffer, tatsächlich ausgesprochene Identifikationen, Fehlzuordnungen, Enthaltungen, Kandidatenabdeckung, Primärbelegabdeckung, Laufzeit und Kosten.
- Rangtreffer und Entscheidungsqualität trennen: richtige Hypothese bei Enthaltung ist kein ausgesprochener Identifikationserfolg. Präzision unter ausgesprochenen Identifikationen zusammen mit Abdeckung berichten, damit reines Enthalten keine scheinbare Verbesserung erzeugt.
- Quoten mit explizitem Nenner und Unsicherheit; ungelöste Labels nicht als Treffer oder nach Belieben als Fehler zählen. Fehler/fehlende Materialien nicht still aus dem Intake-Nenner entfernen. Entwicklungsfälle, retrospektive und unabhängige Kohorten getrennt.
- Mindestens zehn vollständige reale Fälle für den ersten historischen Pilot entsprechend vorhandener Coverage-Grenze anstreben. Zehn sind keine statistische Validierung. Kohortengröße, Abbruchregel, primäre Kennzahl und Mindestverbesserung vor Labelöffnung festlegen.
- Vorschlag für primäre Kennzahl: korrekte Top-1-Identifikationen pro auswertbarem Fall, mit gepaartem Vergleich zur Baseline; Fehlzuordnungen dürfen nicht steigen. Ergänzend Präzision/Abdeckung, Kandidaten-Recall und Konfidenzintervalle berichten. Bei zu wenig unabhängigen Daten oder unklarer Differenz ausdrücklich „Verbesserung nicht nachgewiesen“.
- ADI/LSCC, CRM/Zoom, JPM/GS als bekannte Fehlerregressionen erhalten, nur mit tatsächlich verfügbaren Originalhinweisen und passenden Quellen. Keine neuen erfundenen historischen Rankings. Williams bleibt ungelöst.
- Neue Erkenntnisse mit Datum, Provenienz, ursprünglicher Prognose, späterer Lösung, Fehlerursache und Regression in der zentralen Wissensbasis ergänzen. Nutzer-WKN, bestätigter Basiswert und unabhängig geprüftes Originalprodukt bleiben getrennte Nachweisstufen.

## Verifikation und Übergabe

Je Änderung zuerst passende Regression, dann minimale Implementierung. Ausführen und tatsächliche Ergebnisse dokumentieren:
- python -m pytest -q
- ruff check .
- ruff format --check .
- git diff --check
- Relevante PostgreSQL-Tests ausschließlich gegen wegwerfbare Testdatenbank; übersprungene Tests samt Grund nennen.
- Docker-Build und isolierte CLI-/API-Einzelläufe; keine Serverbereitstellung. Bestehende Markt-Scanner-Routen und Datenverträge auf Regression prüfen.

Liefern: kleiner reviewbarer Draft-PR mit Komponenten-/Änderungsmatrix, wiederverwendeten Modulen, reproduzierbaren Laufbefehlen, tatsächlich erzeugten Artefakthashes, Baselinevergleich, unveränderten Erstprognosen und offenen Blockern. Technische Tests und fachliche Identifikationsabnahme getrennt ausweisen. Keine erfundenen Erfolgsläufe. Wenn Quellenzugriff, historisches Material oder unabhängige Labels fehlen, dies konkret dokumentieren und verbleibende unabhängig umsetzbare Arbeit abschließen. Kein Merge, Deployment oder Order.
