# Echte Websuche und zitierte KI-Quellenauswertung

## Ergebnis und Grenze

Die private Web-Anwendung kann jetzt Tavily als Such-API und OpenAI als Textauswerter
verwenden. Das ersetzt den gesperrten Bing-RSS-Pfad für diese Konfiguration. Die komplette
Kette ist angeschlossen: Teaser verstehen → Suchfragen → Such-URLs → Originalseiten →
Firmenzuordnung und Belegstellen → gemeinsame Kandidatenprüfung → Peer-Suche →
Gegenrecherche → eingefrorener Bericht und Journal.

Ohne eigene API-Zugänge ist die echte Live-Abnahme weiter offen. Die Tests verwenden
kontrollierte HTTP-Antworten, keine behaupteten Live-API-Treffer. Insbesondere wird der
bekannte SLB-Fall nicht als vorab richtige Antwort eingebaut.

## Verarbeitung

- Tavily `/search`: ausdrücklich `basic`, keine automatische Vertiefung, keine generierte
  Antwort und keine übernommenen Volltexte. Nur URLs/Titel dienen als Recherchehinweise.
- Der vorhandene Downloader holt Originalseiten. SSRF-Prüfung, öffentliche HTTPS-Adressen,
  robots.txt, Paywall-Schutz und Rohdatenarchiv bleiben wirksam. Kein Zugang wird umgangen.
- OpenAI Chat Completions, festes Modellprofil `gpt-4.1-mini-2025-04-14`: plant bis zu acht
  spezifische Hinweise/Suchfragen und interpretiert abgerufene Originaltexte.
- Eingabe-WKNs werden vor der KI-Planung entfernt; bekannte Lösungen und Fallregister
  werden nie in die Prompts geladen. API-Ausgaben sind nicht automatisch Tatsachen.
- Zitate müssen wörtlich im Originaltext stehen. Firmenname muss in der Identitätsstelle
  und jeder akzeptierten Belegstelle vorkommen. Ein Ticker braucht eine eigene wörtliche
  Fundstelle; ISIN und Derivatekennungen werden nicht ergänzt.
- KI kann keine Quelle zur Primärquelle erklären. Ihre Befunde stehen separat unter
  `cited_findings` und beeinflussen die Rangfolge nur bei belegter zeitlicher Verfügbarkeit.
  Zu spät revidierte oder zeitlich unsichere Befunde bleiben als Diagnose sichtbar.
- Ohne expliziten historischen Stichtag wird der tatsächliche Wissenszeitpunkt nach den
  Abrufen verwendet. Mit Stichtag bleiben Quellen strikt daran gebunden. Historische
  Blindläufe mit Archivpaketen rufen keine APIs auf.
- KI-Beteiligung bleibt grundsätzlich manuell zu prüfen und sperrt automatische Bestätigung,
  auch wenn lediglich die Identität ergänzt wurde. Ergebnis ist höchstens eine vorläufige
  Hypothese mit Top 3; fünf belegte Gegenkandidaten werden nicht erfunden.

Teaser und ausgewählte öffentliche Quellenauszüge werden an OpenAI gesendet, Suchfragen an
Tavily. Uploads werden weiterhin lokal extrahiert. Verwende nur rechtmäßig bereitgestellte
Inhalte. Prompts, relevante Antworten, Zeitpunkte und Quellenbelege werden privat archiviert;
API-Schlüssel sind keine Promptbestandteile und werden auch bei Reflexion in Antworten aus
Auditdateien entfernt. Modellinterpretationen können trotz echter Zitate semantisch falsch
sein: dies ist keine unabhängige menschliche Verifikation.

## Aufruf- und Kostenkontrolle

Standardmäßig bleiben externe APIs aus. Kostenfreigabe und passende Schlüssel sind getrennt
von der bisherigen internen Web-Anmeldung. Fehlende Freigabe/Schlüssel lösen verständliche
Konfigurationsfehler aus; es gibt keinen heimlichen Rückfall auf einen anderen Bezahlanbieter.

Die eigene persistente Datei `detective/api-budget.db` reserviert atomar vor jedem Aufruf:
5 Cent je Suchaufruf und 10 Cent je KI-Aufruf. Auch unklare/fehlgeschlagene Aufrufe bleiben
reserviert. Der Monatsdeckel liegt technisch bei höchstens 2.000 Cent; ein kleinerer Deckel
ist möglich. Keine automatische Wiederholung, bis zu 16 Such-/12 KI-Aufrufe je Analyse,
40.000 Byte Requestgröße und 2.000 maximale KI-Ausgabetokens. Das Modell ist fest vorgegeben;
es gibt kein automatisches Upgrade auf ein teureres Modell.

Die Originalabrufe sind für Discovery/Peers/Gegenrecherche auf 5/5/1 Dokumente verteilt,
damit die erste Suche nicht alle Auswertungsplätze verbraucht. Das bestehende gemeinsame
HTTP-Limit gilt zusätzlich. Neue externe Aufrufe beginnen nach 180 Sekunden nicht mehr;
ein bereits laufender Abruf kann noch bis zu seinem Timeout dauern.

**Reservierungen sind keine Anbieterrechnung und keine garantierte Euro-Abrechnung.**
Vor Aktivierung müssen die tatsächlichen Tarife sowie Steuern/Währungsumrechnung geprüft
werden. Für die verbindliche 20-EUR-Grenze: keine kostenpflichtige Tavily-Nachbuchung aktivieren,
OpenAI nur mit ausdrücklich genehmigtem kleinem Prepaid-Guthaben betreiben und automatische
Aufladung ausschalten. Bloße Anbieter-Budgetwarnungen sind keine verlässlichen Hard Limits.
Ohne diese Prüfung und Freigabe bleibt die Nutzung gesperrt.

Das Monatsjournal nicht löschen oder durch ein altes Backup zurücksetzen: das würde den
anwendungsinternen Verbrauchszähler zurücksetzen. Bestehende Fallhistorie und Datenbank
werden nicht migriert. Neue Budget-/Auditdaten liegen ausschließlich im eigenen `/data`.

Die geschützte Weboberfläche ergänzt zwei getrennte Provideranzeigen:

- Tavily wird höchstens alle fünf Minuten über den offiziellen `GET /usage`-Endpunkt
  abgefragt. Angezeigt werden Plan, Planlimit, Verbrauch und verbleibende Credits.
- OpenAI stellt den verbleibenden Gratis- oder Prepaid-Kontostand nicht über den
  vorhandenen Projektschlüssel bereit. Die Oberfläche summiert daher nur die im
  privaten API-Audit archivierten Input- und Output-Tokens des laufenden Monats und
  kennzeichnet die daraus berechneten Kosten ausdrücklich als lokale Schätzung.
  Der verbindliche Kontostand bleibt im OpenAI-Billing-Dashboard.

Die OpenAI-Schätzung verwendet für das fest konfigurierte Modell
`gpt-4.1-mini-2025-04-14` die dokumentierten Standardpreise von 0,40 USD je Million
Input-Tokens und 1,60 USD je Million Output-Tokens. Rabatte oder abweichende
Providerabrechnungen werden nicht behauptet.

## Eigene Zugänge einrichten

1. [Tavily-Konto](https://app.tavily.com/) anlegen, API-Schlüssel erzeugen und aktuellen
   kostenlosen Umfang/Nachbuchungseinstellungen prüfen. Keinen Bezahltarif automatisch buchen.
2. [OpenAI-API-Projekt](https://platform.openai.com/api-keys) anlegen und eigenen Projektschlüssel
   erstellen. Das ChatGPT-Abonnement enthält kein API-Guthaben. Bezahlung erst nach Freigabe.
3. Schlüssel ausschließlich in Coolify als geheime **Runtime**-Variablen hinterlegen.
   Nicht als Build-Variablen, nicht im Chat, nicht in Git oder Screenshots.

Offizielle Schnittstellen: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create).
Die tatsächliche Verfügbarkeit des festen OpenAI-Modellprofils muss beim ersten autorisierten
Live-Test geprüft werden. Nicht unterstützte Modelle liefern einen Fehler; keine stille Substitution.

## Coolify: vorbereiten, anschließend ausdrücklich aktivieren

Branch dieser Änderung: `feat/teaser-search-ai`. Vorhandene Domain, `/data`-Speicher,
Web-Passwort und internes Token beibehalten. In Runtime hinzufügen:

| Name | Wert |
|---|---|
| `DETECTIVE_SEARCH_PROVIDER` | `tavily` |
| `DETECTIVE_SEARCH_API_KEY` | eigener Tavily-Schlüssel, geheim |
| `DETECTIVE_SOURCE_AI_ENABLED` | `true` |
| `DETECTIVE_SOURCE_AI_API_KEY` | eigener OpenAI-Schlüssel, geheim |
| `DETECTIVE_API_MONTHLY_BUDGET_EUR` | zunächst `5`, höchstens `20` |
| `DETECTIVE_EXTERNAL_API_APPROVED` | bis zur Freigabe `false` |

Die vorhandene `DETECTIVE_PUBLIC_ALLOW_NETWORK=true` bleibt erforderlich. Erst nach expliziter
Kostenfreigabe und Anbieterprüfung `DETECTIVE_EXTERNAL_API_APPROVED=true` setzen und die eigene
Teaser-Anwendung deployen. Das aktiviert keinen Markt-Worker und keine Orderausführung.

Der geschützte Endpunkt `/api/hebeltrader/runtime` zeigt Provider, Aktivierung und ob die
beiden Schlüssel gesetzt sind, ohne Werte preiszugeben. Bei fehlenden Schlüsseln ist noch
kein voll funktionsfähiger API-Betrieb eingerichtet.

## Tatsächlicher Live-Abnahmelauf nach Einrichtung

- Zuerst einen neuen Fall beziehungsweise den bekannten 198/26 als ausdrücklich bekannten
  Entwicklungsfall analysieren. Ein SLB-Treffer wäre keine neue unabhängige Blindtest-Leistung.
- JSON herunterladen: API-Aufrufe, wörtliche Zitate, Quellen-Zeitpunkte, Top 3, Gegenargumente,
  fünf tatsächlich geprüfte Gegenkandidaten und Budgetreservierungen prüfen.
- Bei Quellenfehlern bleibt der Fall ungelöst. API-/Modellfehler werden sichtbar, nicht als
  erfolgreiche Recherche ausgegeben.
- Danach einen zuvor ungesehenen Teaser analysieren und Erst-Ranking vor Auflösung einfrieren.

Keine Live-API-Aufrufe, kein kostenpflichtiger Tarif und kein produktives Deployment wurden
in dieser Entwicklungsumgebung ausgeführt. Es fehlen Betreiber-Zugangsdaten und Kostenfreigabe.

## Entwicklungsprüfung

797 lokale Tests bestanden, 8 PostgreSQL-Tests übersprungen. Darunter 15 gezielte API-/
Sicherheitstests: offizielle HTTP-Verträge mit MockTransport, ganze Kandidatenpipeline,
literale Zitate, Zeitfilter, KI-Identität, atomare Budgetreservierung und Schlüsselredaktion.
Ruff/Format, JavaScript-Syntax und Docker-Build erfolgreich. Der zusätzliche Docker-API-Smoke
konnte wegen unterbrochener Tool-Aufrufe nicht abgeschlossen werden; kein Erfolg wird behauptet.
Die unabhängige Codeprüfung fand zwei Zeit-/Identitätsprobleme, die mit zunächst fehlschlagenden
Regressionstests korrigiert und nachgeprüft wurden. Live-Abnahme weiterhin offen.
Siehe [JSON-Abnahmebericht](teaser-search-ai-acceptance.json).
