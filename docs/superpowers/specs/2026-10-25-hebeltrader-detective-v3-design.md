# HEBELTRADER-Detektiv V3 – Design

## Zweck

Der Detektiv erhält einen unbekannten Börsenteaser als Text, PDF oder Bild und sucht selbstständig
im tatsächlich verfügbaren Aktienuniversum nach dem beschriebenen Unternehmen. Er liefert bis zu
drei plausible Aktien mit zeitlich zulässigen Belegen, Widersprüchen und offenen Punkten. Er darf
bei unzureichender Evidenz keine Lösung erzwingen.

Der wirtschaftliche Zweck ist eine prüfbare Aktienidentifikation. Derivate werden erst danach und
nur bei unabhängig belegten Produktdaten untersucht. Das Ergebnis ist Research, keine
Kaufempfehlung oder kalibrierte Trefferwahrscheinlichkeit.

## Ziele

- vorhandene SEC-, GLEIF-, FTS5-, News-, OCR-, Provenienz- und Ranking-Komponenten wiederverwenden;
- atomare, überprüfbare Hinweise aus Werbetext extrahieren;
- Kandidaten aus dem gesamten sichtbaren Index statt aus einer Lösungs-Watchlist abrufen;
- Retrieval und Beweisprüfung strikt trennen;
- positive, negative und unbekannte Evidenz gleich nachvollziehbar ausweisen;
- Point-in-Time-Korrektheit bis zur einzelnen Quelle bewahren;
- mindestens einen unveränderten realen Teaser vollständig untersuchen;
- unabhängige Blindtests mit getrennten Eingaben und Lösungen messen;
- innerhalb von 0–20 EUR monatlich und ohne geschützte Inhalte zu umgehen arbeiten.

## Nicht-Ziele und Anti-Ziele

- keine automatische Order, kein Live-Signal und keine Anlageberatung;
- keine WKN aus Prozentwerten, Namenähnlichkeit oder Modellannahmen ableiten;
- keine behauptete weltweite Abdeckung auf Basis des SEC-Universums;
- keine Gleichsetzung eines SEC-Formulars mit einem positiven Unternehmensereignis;
- keine spätere Quelle in einer historischen Analyse verwenden;
- keine Optimierung des Kandidatenkatalogs auf bekannte HEBELTRADER-Lösungen;
- keine Paywall-, Captcha- oder Zugriffsschutzumgehung;
- keine produktive Migration oder Abhängigkeit von PR-#23-Marktdaten für die Identifikation.

## Gewählter Ansatz

### A – Index zuerst, danach Beweisprüfung (gewählt)

Stage A durchsucht den vollständigen zum Stichtag sichtbaren Research-Index und bildet eine breite,
auf höchstens 50 Kandidaten begrenzte Reserve. Stage B prüft diese Reserve anhand normalisierter,
zeitlich zulässiger Evidenz. Dieser Ansatz ist reproduzierbar, günstig und verhindert, dass die
richtige Aktie vor der Suche vorgegeben wird.

### B – freie Webrecherche pro Hinweis (verworfen als Primärweg)

Sie könnte seltene Produkt- oder Kundenhinweise besser abdecken, ist aber schlechter
reproduzierbar, historisch schwerer abzugrenzen und je Quelle rechtlich verschieden. Zulässige,
explizit aktivierte Provider dürfen Stage B später ergänzen; sie ersetzen den Index nicht.

### C – Sprachmodell als Kandidatengenerator (vorerst verworfen)

Das wäre flexibel bei Werbesprache, aber ohne kalibrierte Testbasis nicht ausreichend auditierbar.
V3 bleibt deterministisch. Ein späteres Modell dürfte nur strukturierte Hinweise vorschlagen und
nie Quellenbelege oder Identitäten bestätigen.

## Bestehende Komponenten

V3 erweitert statt ersetzt:

- `scanner/hebeltrader/detective/clues.py` für Textnormalisierung und Kennungstrennung;
- OCR und Uploadgrenzen aus `detective/ocr.py`, `schemas.py` und `service.py`;
- `ResearchIndex` und SQLite FTS5 für das sichtbare Universum und Point-in-Time-Abfragen;
- `IndexedResearchSource`/`IndexedResearchService` für Kandidaten und Evidenz;
- SEC EDGAR für Identitäten, Filings und begrenzte XBRL-Fakten;
- GLEIF ausschließlich als Rechtsträger- und Identitätsquelle;
- normalisierte News-/Issuer-Feed-Evidenz mit Quellenklasse und Verfügbarkeitszeit;
- bestehendes Provenienzarchiv, SHA-Prüfungen, CLI, API und escaped Weboberfläche;
- vorhandene Blind-, Lookahead-, Widerspruchs-, Ausfall- und XSS-Regressionen.

Der heutige `DetectiveService` ruft zwar `search_candidates` auf, bewertet danach aber noch ein
flaches Kandidaten-/Evidenzmodell. V3 macht die Retrieval-Reserve und die folgende Evidenzmatrix zu
expliziten, testbaren Schritten.

## Eingabe und Provenienz

Eine Analyse akzeptiert genau eine oder mehrere dieser Quellen:

- UTF-8-Text;
- PDF, dessen Text seitenweise mit bestehender PDF-Pipeline extrahiert wird;
- PNG/JPEG mit bestehender lokaler Tesseract-OCR.

Für jede Quelle werden SHA-256, Medientyp, Extraktionsmethode, Seitenzahl beziehungsweise
Bildbezug und Zeichenbereiche gespeichert. OCR-Text bleibt überprüfungsbedürftig. Dateinamen und
Verzeichnisnamen dürfen weder als Hinweise noch als Trainingslabel dienen.

API und CLI erzeugen dieselbe normalisierte Anfrage und dieselbe Ergebnisstruktur. Beim API-Start
findet kein Netzwerkzugriff statt. Live-Provider benötigen weiterhin explizite Freigabe,
Konfiguration, Request- und Laufzeitgrenzen.

PDF-Eingaben sind auf 20 MiB und 40 Seiten begrenzt. Die Pipeline verwendet zuerst die vorhandene
Textschicht und OCR nur für Seiten ohne brauchbaren Text. Verschlüsselte, beschädigte oder über den
Grenzen liegende Dokumente werden mit einem expliziten Fehlerstatus abgelehnt. Pro Seite werden
Extraktionsmethode, Erfolgsstatus und Warnungen gespeichert; ein teilweiser OCR-Erfolg darf nicht
als vollständig extrahiertes Dokument erscheinen.

## Hinweisextraktion

### Atomarer Hinweis

Jeder extrahierte Hinweis enthält:

- `clue_id` als deterministischen Hash;
- Kategorie und normalisierte Aussage;
- Originalzitat, Quelle, Seite und Zeichenbereich;
- Instrumentbereich `stock`, `derivative`, `ambiguous` oder `promotional`;
- Wert, Einheit, Vergleichsperiode und Bezugsdatum, soweit ausdrücklich vorhanden;
- Polarität `asserted`, `negated` oder `unknown`;
- Extraktionsmethode und Konfidenzklasse;
- `requires_manual_review`.

### Kategorien

- Branche, Geschäftsfeld, Produkte und Technologien;
- Marktstellung und geografische Hinweise;
- Umsatz, Ergebnis, Marge, Cashflow und deren Veränderung;
- Prognosen und Analystenrevisionen;
- Übernahmen, Beteiligungen, Zulassungen, Aufträge und Partnerschaften;
- ausdrücklich genannte Kunden oder Geschäftspartner;
- Börsenplatz, Land, Marktkapitalisierung und Identifikatoren;
- Datums-, Quartals- und relative Zeitangaben.

### Werbesprache und Prozentwerte

Prozentangaben werden nur einer fundamentalen Kennzahl zugeordnet, wenn derselbe Satz oder ein
eindeutiger Tabellenkontext eine unterstützte Kennzahl, Periode und Bezugsgröße enthält. Muster wie
„1.091 % Gewinnchance“, „1.717 % mit diesem Call“ oder „2.631 % Rendite“ werden als
`promotional_derivative_return` klassifiziert. Sie dürfen weder Umsatz-/Gewinnwachstum noch
Marge, Score oder Kandidatensuche beeinflussen.

Superlative wie „einmalige Chance“, „Weltmarktführer“ oder „explodiert“ bleiben Werbesprache,
solange keine Quelle eine eng definierte, messbare Aussage belegt. Fehlende Werte werden nicht
ergänzt.

## Stage A – Candidate Retrieval

Der Retriever erstellt aus den belastbaren Hinweisen mehrere unabhängige FTS-/Strukturabfragen:

1. Branche und Geschäftstätigkeit;
2. Produkte, Technologie und benannte Entitäten;
3. Land, Börsenplatz und Größenklasse;
4. unterstützte Fakten und Ereignisse;
5. zeitlich passende Meldungsbegriffe.

Die Ergebnismengen werden vereinigt, dedupliziert und anhand offen ausgewiesener Retrievalsignale
sortiert. Keine Abfrage enthält die spätere Lösung, sofern sie nicht ausdrücklich im Teaser steht.
Ein exakter Aktienidentifikator darf einen Kandidaten hoch priorisieren; eine Derivate-WKN darf
keine Aktienidentität erzeugen.

Jeder Retrievalkanal liefert höchstens 50 Treffer. Die Ranglisten werden deterministisch mit
Reciprocal Rank Fusion (`k=60`) zusammengeführt. Danach gelten feste, vor den Blindtests
eingefrorene Strukturbeiträge: Land `+8`, SIC-/Branchenhinweis `+20`, belegtes Ereignis `+25`,
ausdrücklicher Aktienidentifikator `+100`, reine Identitäts-Textähnlichkeit höchstens `+3`, harter
Widerspruch `-25` und bekanntes Fonds-/Nicht-Aktieninstrument `-50`. Gleichstände werden nach
stabiler Asset-ID aufgelöst. Änderungen an Gewichten erzeugen eine neue Modellversion und dürfen
nicht rückwirkend in denselben Benchmarkbericht einfließen.

Die Reserve enthält höchstens 50 Aktienkandidaten. Bekannte Fonds und sonstige Instrumente werden
ausgeschlossen und separat ausgewiesen. Ein unbekannter Instrumenttyp bleibt mit dem Hinweis
`instrument_type_unverified` in der Reserve, weil der vorhandene SEC-Index viele Emittenten noch
nicht sicher als operative Aktie klassifiziert. Der Bericht nennt:

- vollständige und sichtbare Universumsgröße;
- untersuchte Kandidatenzahl und Abdeckungsquote;
- verwendete Abfragen und Treffer je Kanal;
- ausgelassene Märkte und fehlende Datenfelder;
- Grund für `insufficiently_constrained`, falls keine sinnvolle Vorauswahl möglich ist.

Besteht ein Teaser nur aus allgemeiner Werbesprache oder aus nicht überprüfbaren Aussagen und
liefert keine belastbare strukturierte Einschränkung, endet Stage A als
`insufficiently_constrained`; zufällige FTS-Treffer werden dann nicht als Top-3-Identifikation
ausgegeben.

Stage A kennt keine Blindtestlösung und lädt keine Lösungsdatei.

## Stage B – Evidence Verification

Für jeden Stage-A-Kandidaten entsteht eine Matrix aus allen atomaren Hinweisen. Jede Zelle hat
genau einen Zustand:

- `confirmed`: eine zeitlich zulässige Quelle belegt die konkrete Aussage;
- `contradicted`: eine zeitlich zulässige Quelle widerlegt sie konkret;
- `unknown`: Daten fehlen oder die Aussage ist nicht eindeutig prüfbar.

`unknown` zählt weder positiv noch negativ. Ein bekannt falsches Land, eine falsche Branche oder
eine widersprochene Kennzahl senkt das Ranking stärker als ein schwacher Texttreffer es erhöht.
Mehrfach verbreitete Meldungen desselben Ursprungs zählen als ein Evidenzcluster. Zwei Belege sind
nur unabhängig, wenn ihre `origin_id` verschieden ist und keiner den anderen beziehungsweise
dieselbe Ursprungsmeldung übernimmt. Meldungen zum selben Unternehmen und Ereignistyp innerhalb
von 48 Stunden mit identischem oder nahezu identischem normalisiertem Inhalt werden geclustert.
Ein SEC-Dokument und Portale, die dieses Dokument lediglich wiedergeben, sind daher eine Quelle,
nicht mehrere Bestätigungen.

Belege enthalten Quellen-ID, URL, Quellenklasse, Originalfundstelle, Ereigniszeit,
Erstveröffentlichung, historische Verfügbarkeit, Abrufzeit und Content-SHA. SEC-Formulare bleiben
Dokumentereignisse; eine Gewinnsteigerung oder Prognoseanhebung zählt erst nach deterministischer
Faktenextraktion.

Mit der vorhandenen Datenbasis zuverlässig prüfbar sind Land, SEC-Identität, SIC als enger
Branchenhinweis, ausgewählte XBRL-Fakten wie Umsatz und Nettoergebnis sowie bereits normalisierte
Ereignisse. Produkte, konkrete Kunden/Partner, Marktstellung, freie Geschäftsbeschreibungen und
historische Marktkapitalisierung bleiben `unknown`, solange dafür kein zeitlich archivierter
Primärbeleg vorhanden ist. V3 berechnet keine historische Marktkapitalisierung aus heutigen
Aktienzahlen oder später geladenen Kursen.

Das Ranking verwendet dokumentierte ganzzahlige Gewichte und nennt es
`evidence_score_not_probability`. Zusätzlich werden Evidenzbreite, Widerspruchszahl und
Quellenabdeckung ausgewiesen. Eine Prozentwahrscheinlichkeit ist erst nach unabhängiger
Kalibrierung zulässig und gehört nicht zu V3.

Für historische Analysen ist die Teaser-Publikationszeit verpflichtend. Fehlt sie, endet der Lauf
mit `unresolved` und `missing_publication_time`; Abruf- oder Dateizeit dürfen sie nicht ersetzen.
Zeitpunkte werden nach UTC normalisiert, während relative Angaben zunächst in der belegten
Originalzeitzone aufgelöst werden. Evidenz ohne nachweisbares `available_at` wird aus historischen
Läufen ausgeschlossen. Eine heute abgerufene Identität belegt nicht automatisch ihre historische
Gültigkeit.

## Entscheidung und Ausgabe

Die Ausgabe enthält höchstens drei Kandidaten mit:

- Identität und Börsennotierung;
- Retrievalgründen;
- bestätigten, widersprochenen und unbekannten Hinweisen;
- Quellen und Zeitbelegen;
- Datenabdeckung und Auslassungen;
- unkalibriertem Evidenzscore;
- fehlenden Voraussetzungen für eine Bestätigung.

Gesamtstatus mit vor den Blindtests eingefrorenen Schwellen:

- `likely_candidate`: mindestens drei bestätigte Hinweise aus mindestens zwei Kategorien,
  mindestens zwei unabhängige Evidenzcluster einschließlich eines Primärbelegs, kein harter
  Widerspruch und mindestens 20 Punkte Abstand zum zweitplatzierten Kandidaten;
- `unclear`: mindestens ein Kandidat besitzt konkrete Evidenz, erfüllt aber die Schwellen oder den
  Abstand für `likely_candidate` nicht;
- `unresolved`: die Suche ist unzureichend eingeschränkt, kein Kandidat besitzt einen konkreten
  Beleg oder alle führenden Kandidaten haben einen harten Widerspruch.

Als harter Widerspruch gelten eine belegbar falsche ausdrücklich geforderte Jurisdiktion, ein
belegbar unvereinbares Instrument, eine außerhalb der angegebenen Toleranz liegende konkrete
Kennzahl/Periode oder ein belegtes Ereignis nach dem zulässigen Stichtag. Unbekannte Branche oder
fehlende Daten sind kein Widerspruch. `likely_candidate` bleibt eine manuell zu prüfende
Research-Einstufung, keine Bestätigung oder Anlageempfehlung.

## Derivate und WKN

Aktien- und Derivatekennungen verwenden getrennte Typen und Felder. Erst nach der Aktienanalyse
wird eine ausdrücklich im Teaser vorhandene Derivate-WKN gegen unabhängige Produktdaten geprüft.
Erforderlich sind mindestens Emittent, Basiswert, Produktart, ISIN/WKN, Bezugsverhältnis,
Basispreis, Laufzeit beziehungsweise Open End und Quellenfundstelle. Ohne zeitlich gültige
Emittenten- oder Börsenquelle lautet der Status `unresolved_product_identifier`.

Eine fehlende Produkt-WKN wird niemals geraten. Renditeprozente, Aktienkennungen und ähnliche
alphanumerische Texte dürfen keine Produktkennung erzeugen.

## Historische Blindtests

### Trennung

Ein Fall besteht aus zwei getrennten Dateien:

- Eingabe: unveränderter Teaser, Publikationszeit, Quell-SHA und zulässiger Text-/Bild-/PDF-Beleg;
- Lösung: bestätigte Aktie, Lösungsquelle, Reviewer und Bestätigungszeit.

Scanner und Evaluator laufen als getrennte Prozesse. Der Scanner erhält weder Lösungsdatei noch
Lösungspfad, Umgebungsvariable oder Mount; er schreibt zunächst unveränderliche Rankings. Erst
danach lädt der Evaluator die Lösungen und verknüpft sie über zufällige Fall-IDs. Dateinamen
enthalten keine Firma, Ticker, WKN oder ISIN. Ein Integritätstest sucht Lösungskennungen im
Eingabekorpus und bricht bei Leakage ab.

### Korpus

Ziel sind 10–20 echte, unveränderte Fälle aus unterschiedlichen Branchen und Zeiträumen, soweit
Originalmaterial und Nutzungsrechte verfügbar sind. Die vorhandenen zehn synthetischen
V2.4-Fälle bleiben reine Funktionstests. Bekannte HEBELTRADER-Fälle dürfen Teil des Korpus sein,
aber weder Retrievalkatalog noch Gewichtung anhand ihrer Lösungen erhalten.

Gemessen werden Top-1, Top-3, falsche Zuordnung, Enthaltung, nicht erfasste Aktie,
Quellenabdeckung, Laufzeit, Requests und Kosten. Ergebnisse werden getrennt nach echten und
synthetischen Fällen veröffentlicht. Mindestens zehn synthetische oder offen lizenzierte Fälle
sichern die Funktion; sie zählen nicht als reale Erkennungsleistung. Liegen weniger als zehn echte
Originalteaser mit getrennt belegter Lösung vor, lautet der reale Benchmarkstatus
`insufficient_real_benchmark_coverage`. Ein kleines Korpus wird nicht als globale Güte ausgegeben.

## Realer Praxistest

Mindestens ein tatsächlich vorhandener Teaser wird vollständig offline oder mit ausdrücklich
freigegebenen Providern untersucht. Der Bericht enthält Originalhinweise, Stage-A-Reserve,
geprüfte Quellen, Positiv- und Negativbelege, Top 3, Endstatus und Unsicherheiten.

Bevorzugte Quelle ist ein unveränderter Teaser aus dem vorhandenen HEBELTRADER-Bestand auf
Hetzner. Falls das Original in der Entwicklungsumgebung fehlt, wird kein echter Erfolg simuliert.
Stattdessen liefert der PR einen read-only Docker-Befehl, der den originalen Serverbestand nutzt;
der reale Bericht wird erst nach diesem Lauf dokumentiert.

Ein echter Fall ist nur abnahmefähig, wenn Originaldatei, SHA-256, belegte Publikationszeit und
Nutzungsstatus vorliegen und die Lösung separat durch eine unabhängige Quelle, Reviewer und
Bestätigungszeit dokumentiert ist. Fehlt eines dieser Elemente, bleibt der Praxistest
`pending_external_material` und darf nicht als erfolgreicher realer End-to-End-Test erscheinen.

## Schnittstellen und geplante Dateien

- `detective/clues.py`: atomare, instrumentbezogene Hinweisextraktion;
- `detective/retrieval.py`: Multi-Query-Stage A über `ResearchIndex`;
- `detective/verification.py`: dreiwertige Evidenzmatrix und Clustergewichtung;
- `detective/service.py`: Orchestrierung, Status und gemeinsame API-/CLI-Ausgabe;
- `detective/schemas.py`: versionierte Eingabe-, Hinweis-, Kandidaten- und Ergebnisverträge;
- `research_index/repository.py`: nur gezielte, rückwärtskompatible Suchabfragen;
- `research_benchmark.py`: strikt getrennte Blindtestauswertung;
- `tests/fixtures/detective-v3/`: ausschließlich synthetische/offen lizenzierte Eingaben;
- `docs/hebeltrader-detective-v3.md`: Quellenabdeckung, Betrieb und reale Abnahme.

Bestehende Datenbankschemata werden nur lokal und additiv geändert, falls FTS-Felder zwingend
erforderlich sind. Eine produktive Migration ist nicht Bestandteil des PR.

## Sicherheit, Grenzen und Fehlerverhalten

- kein Netzwerk beim API-Start oder im Offline-Modus;
- harte Request-, Laufzeit-, Antwortgrößen- und Kostenlimits;
- keine Secrets in Logs, Reports, Commits oder Containern;
- XSS-sichere Templateausgabe und keine ungefilterte HTML-Wiedergabe aus Teasern/Quellen;
- Providerfehler blockieren nicht den gesamten Lauf, erscheinen aber in Coverage und Ergebnis;
- Quellen ohne geklärte automatisierte Zugriffsrechte bleiben deaktiviert;
- PostgreSQL, Original-PDFs, Immich und bestehende Archive bleiben unverändert.

## Abnahme

V3 ist technisch abgenommen, wenn:

1. Text, PDF und Bild dieselbe normalisierte Pipeline erreichen;
2. Derivatewerbeprozente in Regressionen nie zu fundamentalen Fakten werden;
3. Stage A das vollständige sichtbare Universum durchsucht und höchstens 50 Kandidaten liefert;
4. Stage B bestätigte, widersprochene und unbekannte Hinweise getrennt ausweist;
5. spätere oder korrigierte Evidenz vor ihrer Verfügbarkeit ausgeschlossen bleibt;
6. Aktien- und Derivatekennung strikt getrennt bleiben;
7. zehn unabhängige Funktionstestfälle ohne Lösungsleakage reproduzierbar laufen;
8. mindestens ein echter Originalteaser ausgeführt und ehrlich bewertet wurde;
9. Ruff, pytest, Docker-Build und GitHub Actions erfolgreich sind;
10. der PR keinen Merge, kein Deployment, keine Buchung und keine produktive Datenänderung enthält.

Die fachliche Abnahme „tatsächlich verwendbar“ erfordert zusätzlich echte Top-1-/Top-3-Messwerte
auf dem getrennten Korpus. Ohne verfügbare Primärquellen darf ein korrektes `unresolved` nicht als
Fehler kaschiert werden.
