# HEBELTRADER – Identifikationsregeln und Fallregister

Stand: 2026-10-28. Verantwortlich für die inhaltliche Fortführung: ChatGPT bei ausdrücklichen Folgeaufträgen. **Keine automatische Hintergrund-Synchronisierung.**

## Zweck und Evidenzstatus

Dieses Register ist die versionierte, überprüfbare Wissensbasis für Rudolf-Wittmer-/HEBELTRADER-Teaser. Es trennt (a) vom Nutzer ausdrücklich aufgelöste Fälle, (b) früher im Gespräch berichtete Zuordnungen mit unvollständigem Originalbeleg, (c) Fehlversuche und (d) offene Fälle. Eine Optionsschein-WKN ist **nicht** die Aktien-WKN. Ein vom Nutzer genannter Call gilt als Nutzer-Auflösung, nicht als unabhängig verifizierte Produktstammdaten-Prüfung. Unbekannte Felder bleiben **unbekannt**. Vollständige Originalteaser dürfen nur aus autorisierten Quellen übernommen werden; kurze Auszüge/Paraphrasen genügen für dieses Register.

## Verbindliche Identifikationsmethode

1. Originalteaser, Datum, Ausgabe, Überschrift, exakten Wortlaut, beworbene Rendite und Herkunft getrennt erfassen. Fehlende Angaben markieren.
2. Weltweite Kandidatensuche statt Branchen-/US-Vorfilter; **mindestens fünf ernsthafte Gegenkandidaten** aktiv prüfen, soweit genügend plausibel sind. Weniger nur mit expliziter Begründung.
3. Unternehmensspezifische Ereignisse (konkrete Übernahmen, Produkte, Partner, Zahlen und zeitliche Koinzidenz) vor generischen KI-/Saisonalitäts-/Chart-Floskeln gewichten. Nicht aus einem einzigen gemeinsamen Schlagwort auf den Titel schließen.
4. Jeden Kernhinweis mit historisch passender **Primärquelle** und Publikationsdatum abgleichen; Quellen erst nach Teaser-Veröffentlichung dürfen nicht als damals bekannte Evidenz gelten.
5. Für Top 3 identische Matrix führen: bestätigt / widersprochen / unbekannt; belegte Gegenargumente und alternative Erklärungen. Ein harter Widerspruch schlägt zahlreiche generische Übereinstimmungen.
6. **Aktive Falsifikation:** Was müsste wahr sein, damit Platz 2 statt Platz 1 zutrifft? Vor Entscheidung gezielt danach suchen. Erst nach vollständigem Gegenkandidatenvergleich Rangfolge und begründete Konfidenz veröffentlichen.
7. Prozent-Konfidenz nur mit validierter Kalibrierung; sonst „hoch/mittel/niedrig“ und offene Belege. Bei fehlenden spezifischen Belegen: ungelöst, keine erzwungene Lösung.
8. Aktienidentifikation und Derivatesuche strikt trennen. Teaser-Rendite (z. B. 1.191 %) ist **Werbeaussage**, kein fundamentaler Indikator, keine eindeutig ableitbare WKN und kein prognostizierter Gewinn.
9. Vor jeder Optionsschein-Handelsempfehlung Produktidentität, Emittent, ISIN/WKN, Basispreis, Laufzeit, Bezugsverhältnis, Quotierung, Spread, Handelbarkeit in Österreich und Risiko **unabhängig** prüfen.
10. Jeder nachträglich aufgelöste Fall wird als Blindtest protokolliert: ursprüngliche Rangliste **unverändert**, Auflösung mit Quelle, Fehlerursache, korrigierte Regeln und Regressionstest. Keine rückwirkende Schönung der Trefferquote.
11. Unaufgelöste Fälle bleiben im Register. „Nicht bekannt“ ist kein Fehlalarm und keine erfolgreiche Identifikation.
12. Keine Erfolgsquote ohne vollständig datierten, nachvollziehbaren Nenner; frühere aggregierte Erinnerungszahlen sind nicht automatisch belastbare Benchmarks.

## Fallregister – 18 dokumentierte Teaser-Fälle (15 ursprüngliche Fälle + JPMorgan Chase + Johnson & Johnson + Analog Devices)

Die aktuellen Werte stammen aus der ergänzten Nutzerrekonstruktion. Die bestehenden
HT-IDs bleiben stabil; `reference_number` in der JSON-Datei entspricht Fall 01–18 im
neuen Auftrag. [Strukturierte Referenzen](../data/hebeltrader/teaser-cases.json).
Vorheriger Tabellenstand: [datierter Provenienz-Snapshot](archive/hebeltrader-register-before-reference-refresh-2026-10-28.md).
Auflösungsdatum und Veröffentlichungsdatum sind getrennt; alle ursprünglichen Top-3-Listen
und genauen Veröffentlichungsuhrzeiten bleiben unbekannt.

| ID | Teaser / Kontext | Aktie / Ticker | Call-WKN | Status / Beleg | Besondere Umstände und offene Felder |
|---|---|---|---|---|---|
| HT-001 | „Chip-Gigant im Ausnahmezustand: Die Gewinnmaschine läuft auf Hochtouren!“; HEBELTRADER 200/26; 28.10.2026 | Analog Devices (ADI) | MN84GA | FALSCH (Nutzerrekonstruktion) | Ersttipp: Lattice Semiconductor. Nutzerfall 18. Historische unkalibrierte Angabe: 95 %. Ankereffekt und Bestätigungssuche nach frühem Lattice-Tipp; spezifische Unternehmensereignisse hätten stärker geprüft werden müssen; unkalibrierte 95-%-Angabe. Volltext vorhanden. |
| HT-002 | „Gewinnstärke, Kaufsignal, Turbo-Hebel – das Setup für den Volltreffer!“; HEBELTRADER 190/26; 14.10.2026 | Zurich Insurance Group | UN6E7X | FALSCH (Nutzerrekonstruktion) | Ersttipp: UnitedHealth Group. Nutzerfall 03. Allgemeine Gewinn- und defensive Branchenhinweise waren nicht spezifisch genug. Volltext vorhanden. |
| HT-003 | „Wachstum ohne Ende – Handels-Gigant vor der Mega-Aufholjagd!“; HEBELTRADER 192/26; 16.10.2026 | Costco Wholesale (COST) | JY55QZ | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Costco. Nutzerfall 01.  Volltext vorhanden. |
| HT-004 | „Comeback mit Ansage: Dieser Tech-Titel startet durch!“; HEBELTRADER 176/26; 24.09.2026 | Salesforce (CRM) | JG0AEJ | FALSCH (Nutzerrekonstruktion) | Ersttipp: Zoom. Nutzerfall 04. Generisches Tech-Comeback-Narrativ überbewertet. Volltext vorhanden. |
| HT-005 | „Gewinnsprung voraus: Der unterschätzte KI-Profiteur!“; HEBELTRADER 173/26; 21.09.2026 | Micron Technology (MU) | UN87G6 | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Micron. Nutzerfall 05.  Volltext vorhanden. |
| HT-006 | „Gesundheitsriese vor der Neubewertung!“; HEBELTRADER 161/26; 03.09.2026 | UnitedHealth Group (UNH) | VH2LU2 | RICHTIG (Nutzerrekonstruktion) | Ersttipp: UnitedHealth. Nutzerfall 06.  Volltext vorhanden. |
| HT-007 | „Cloud, Strom und Kühlung: Hier liegt der Schlüssel zum nächsten KI-Schub!“; HEBELTRADER 157/26; 28.08.2026 | Vertiv Holdings (VRT) | HM4EB1 | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Vertiv. Nutzerfall 07.  Volltext vorhanden. |
| HT-008 | „KI, Infrastruktur, Milliarden – diese Aktie hat den perfekten Mix!“; HEBELTRADER 147/26; 14.08.2026 | KKR & Co. (KKR) | VH62T5 | RICHTIG (Nutzerrekonstruktion) | Ersttipp: KKR. Nutzerfall 10.  Volltext vorhanden. |
| HT-009 | „Diese Comeback-Aktie könnte jetzt alles in den Schatten stellen!“; HEBELTRADER 144/26; 11.08.2026 | Pfizer (PFE) | WA4R5Q | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Pfizer. Nutzerfall 11.  Volltext vorhanden. |
| HT-010 | „Ausbruchsalarm bei einem Hightech-Schwergewicht!“; HEBELTRADER 143/26; 10.08.2026 | Broadcom (AVGO) | MN8GZP | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Broadcom. Nutzerfall 12.  Volltext vorhanden. |
| HT-011 | „Hightech-Konzern vor neuem Rekordhoch!“; HEBELTRADER 140/26; 05.08.2026 | Thales | DN3NVH | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Thales. Nutzerfall 14.  Volltext vorhanden. |
| HT-012 | „Hier steckt eine irrwitzige Turnaround-Chance drin!“; HEBELTRADER 137/26; 31.07.2026 | BASF | MJ7DUX | RICHTIG (Nutzerrekonstruktion) | Ersttipp: BASF. Nutzerfall 15.  Volltext vorhanden. |
| HT-013 | „Fundamental stark, charttechnisch explosiv: Die nächste Rallye kündigt sich an!“; HEBELTRADER 154/26; 25.08.2026 | Danaher (DHR) | JY3SF7 | FALSCH (Nutzerrekonstruktion) | Ersttipp: Zebra Technologies. Nutzerfall 08. Allgemeine fundamentale und charttechnische Aussagen reichten nicht zur eindeutigen Identifikation. Volltext vorhanden. |
| HT-014 | „Hier braut sich eine Comeback-Story mit rekordverdächtigem Hebelpotenzial zusammen!“; HEBELTRADER 151/26; 20.08.2026 | SAP | UP9A9X | FALSCH (Nutzerrekonstruktion) | Ersttipp: Oracle. Nutzerfall 09. Oracle statt SAP; direkte Software-Wettbewerber und konkrete Geschäftszahlen gegeneinander prüfen. Volltext vorhanden. |
| HT-015 | „Dieser Rüstungs-Highflyer startet durch – mit explosivem Turbo-Potenzial!“; HEBELTRADER 141/26; 06.08.2026 | Leonardo S.p.A. | VJ2RFH | FALSCH (Nutzerrekonstruktion) | Ersttipp: Thales. Nutzerfall 13. Thales statt Leonardo; konkrete Aufträge, Ereignisse und Kennzahlen müssen zwischen europäischen Rüstungskonzernen entscheiden. Volltext vorhanden. |
| HT-016 | „Dieser Branchenführer profitiert vom Stromhunger der Zukunft!“ | Auflösung unbekannt; Verdacht: Williams Companies | unbekannt | Ungelöst | Ersttipp: Williams. Nutzerfall 02.  Vollständiger Originalteaser fehlt. |
| HT-017 | „Die Rallye hat begonnen – Wall-Street-Schwergewicht im Ausbruch!“; HEBELTRADER 193/26; 19.10.2026 | JPMorgan Chase (JPM) | MN6CYX | FALSCH (Nutzerrekonstruktion) | Ersttipp: Goldman Sachs. Nutzerfall 16. Historische unkalibrierte Angabe: 60 %. Zu frühe Festlegung auf Goldman Sachs aufgrund allgemeiner Rallye-Hinweise; unkalibrierte 60-%-Angabe. Volltext vorhanden. Auflösung am 2026-10-19. |
| HT-018 | „Rekordjagd im Gesundheitssektor – dieser Titel gehört ins Depot!“; HEBELTRADER 195/26; 21.10.2026 | Johnson & Johnson (JNJ) | JE11C1 | RICHTIG (Nutzerrekonstruktion) | Ersttipp: Johnson & Johnson. Nutzerfall 17. Historische unkalibrierte Angabe: 55 %.  Volltext vorhanden. Auflösung am 2026-10-21. |

### Weitere genannte WKNs – **noch keinem Teaser belastbar zugeordnet**

**HM43B1.** Diese Codes sind aus früheren Diskussionen bekannt, aber ohne geprüfte Teaser-/Aktien-Zuordnung. Nicht als bestätigte Treffer zählen.

**FG8HCH:** In einer früheren Unterhaltung als gekaufter alternativer Nasdaq-Inc.-Call (500 Stück) erwähnt; **nicht** als beworbene Original-WKN eines HEBELTRADER-Teasers bestätigt. Nicht in die Trefferquote aufnehmen.

### Rekonstruierte Bilanz der bisherigen Blindtests

Die **ursprünglichen 15 Fälle**: 9 richtig, 5 falsch, 1 ungelöst (**Williams**, Nr. 2). Damit zunächst 14 abgeschlossene Identifikationen. Der frühere Wert 9/14 = 64,3 % bezog sich ausschließlich auf die abgeschlossenen Fälle.

- **19.10.2026, Check 16:** JPMorgan Chase / MN6CYX, Ersttipp Goldman Sachs → **falsch**. Bilanz: 9 richtig, 6 falsch, 1 ungelöst = 16 erfasste Fälle, davon 15 abgeschlossen.
- **21.10.2026, Check 17:** Johnson & Johnson / JE11C1 → **richtig**. Bilanz: 10 richtig, 6 falsch, 1 ungelöst = 17 erfasste Fälle, davon 16 abgeschlossen. Die damalige Angabe „10 richtig / 6 falsch / 16 Tests = 62,5 %“ bezog sich auf die **abgeschlossenen** Tests und schloss Williams aus.
- **28.10.2026:** Analog Devices / MN84GA; Ersttipp Lattice Semiconductor → **falsch**.

**Aktueller Stand: 18 erfasste Fälle, davon 17 aufgelöst: 10 richtig, 7 falsch, 1 ungelöst.** Trefferquote abgeschlossener Fälle: **10/17 = 58,8 %**; bezogen auf alle erfassten Fälle: **10/18 = 55,6 %**. Das sind rekonstruierte Gesprächsangaben, **kein unabhängig validierter Benchmark**. Für fehlende Originalteaser und Rankings dürfen keine Details erfunden werden.

## Fehlerprotokoll

### FE-001 – Lattice statt Analog Devices (28.10.2026)
- **Ursprüngliche Antwort:** Lattice Semiconductor / LSCC, mit unbegründeten 95 %.
- **Tatsächliche Nutzerauflösung:** Analog Devices / ADI, Call MN84GA.
- **Ursache:** Ankereffekt; Bestätigungsfehler; generische Übereinstimmungen bei KI, Margen und Umsatz überbewertet; nicht mindestens fünf Alternativen geprüft; die spezifische **Kombination Empower + Alif** nicht vorrangig abgeglichen.
- **Folgefehler:** Recherche und mögliche Handelsvorbereitung für Optionsscheine auf den **falschen Basiswert** Lattice.
- **Regressionstest:** ADI muss vor LSCC stehen, wenn die ursprünglichen spezifischen Teaserhinweise mit zeitlich passenden Primärquellen vorliegen; falsche 95-%-Konfidenz verhindern.

### FE-002 – Zoom statt Salesforce (24.09.2026)
- **Ursprüngliche Antwort:** Zoom.
- **Tatsächliche Nutzerauflösung:** Salesforce / CRM, Call JG0AEJ.
- **Ursache noch nicht hinreichend belegt:** vermutlich zu frühe Gewichtung des generischen „Comeback“-Narrativs; genaue damalige Quellen und Ranking rekonstruieren, nicht rückwirkend erfinden.
- **Regressionstest:** Originalteaser 176/26 unverändert prüfen und Salesforce mit mindestens fünf Alternativen vergleichen.

## Offene Erfassungs- und Verifikationsaufgaben

- Vollständige, autorisiert verfügbare historische Blindtest-Protokolle einschließlich **aller falschen und ungelösten** Fälle rekonstruieren; **keine** erfundenen Teaser-Überschriften oder Datierungen.
- Originalüberschriften, Ausgaben, Datumsangaben, konkrete Katalysatoren und damalige Ranglisten zu HT-002/003 und HT-005 bis HT-012 nachtragen.
- Historische Fallstatistik anhand tatsächlich vollständig erfasster Einzelbeispiele neu berechnen.
- MN84GA und weitere Produkt-WKNs unabhängig anhand zeitgestempelter Emittenten-Produktblätter prüfen.
- Diese Datei mit dem existierenden `docs/hebeltrader-detective-v3.md` und echten, getrennt gehaltenen Blindtest-Fixtures verbinden; keine Lösung in die Scanner-Eingabe leaken.
- Änderungen in Git mit Datum, Evidenzherkunft und Änderungsgrund versionieren. Jeder neue Teaser erhält sofort einen Fall-Eintrag, auch wenn ungelöst.

## Änderungsjournal

- **2026-10-28 (erneute Vollständigkeitsprüfung):** Historische Check-16-/Check-17-Auflösungen ergänzt: JPMorgan Chase MN6CYX (Ersttipp Goldman Sachs falsch) und Johnson & Johnson JE11C1 (richtig). 18 Fälle insgesamt, 10 richtig, 7 falsch, 1 ungelöst; historische Quote 10/16 vor Analog Devices bezog sich auf abgeschlossene Fälle ohne Williams.
- **2026-10-28 (Korrektur):** Vier fehlende Fälle Danaher, SAP, Leonardo und Williams nachgetragen; Gesamtbestand 16; historische Ersttest-Bilanz 9 richtig, 6 falsch, 1 offen; Zuordnung von JY3SF7, UP9A9X, VJ2RFH ergänzt; BASF-WKN auf MJ7DUX korrigiert.
- **2026-10-28:** Initiale Wissensbasis aus dokumentierten Gesprächsauflösungen, früherer Fallübersicht und bestehender Repository-Dokumentation angelegt. Fall HT-001 samt Fehleranalyse und verbindlicher Gegenkandidatenregel aufgenommen. Historische unvollständige Fälle ausdrücklich gekennzeichnet.

## Integration und allgemeine Fehlerregeln (28.10.2026)

Der neue [Primärworkflow](hebeltrader-primary.md) verwendet dieses Register ausschließlich
im getrennten Inventar-/Auswertungsschritt. Die Kandidatenrecherche liest keine Lösungen.
Alle 18 Einträge bleiben Entwicklungsfälle; fehlende Originaltexte und Ranglisten werden
nicht rekonstruiert oder als unabhängige Blindtests ausgegeben.

Aus den dokumentierten Fehlern folgen allgemeine Prüfregeln, keine fest eingebauten
Gewinnernamen: konkrete Unternehmensereignisse vor Werbeformulierungen; Beteiligung nicht
als Übernahme bestätigen; Kennzahlen an Unternehmen und Berichtsperiode binden; mindestens
fünf belegte Gegenkandidaten; gezielte Gegenrecherche; bei Lücken Enthaltung. Die konkreten
ADI/CRM/JPM/JNJ-Auflösungen sind keine Ranglistenregeln. Williams bleibt ungelöst.

Originalranglisten werden vor jeder späteren Auflösung eingefroren. Eine nachträgliche
Auflösung macht einen bereits bekannten Entwicklungsfall nicht zu einem unabhängigen Test.
Das Register wird nicht automatisch um angeblich bestätigte Lösungen ergänzt.


## V3.1 – automatisch protokollierte neue Fälle

Die folgenden Erweiterungen sind append-only Journalexporte. Sie ändern keinen der
18 historischen Einträge. Andere Autoren werden ausdrücklich getrennt ausgewiesen.

<!-- TI-JOURNAL:51a2e4a819c71658a7259c9bd34ef56d90f552009d4f71926fca0d9b4b6f1d4a -->
### TI-282b503c1ac7bf3c491f – intake – 2026-10-28T13:21:49.993600+00:00

```json
{"content_key": "12b0f6f946d8ab533a5597b0b3f0d154b5020267c0aeb801f1c24437adbc6e14", "input": {"advertised_return": null, "author": "Alfred Maydorn", "evaluation_class": "retrospective", "headline": "Doppelter Verzehnfacher: Beste Aktie, Top-Krytowährung", "issue": "", "original_source_url": "https://www.deraktionaer.de/artikel/aktien/doppelter-verzehnfacher-beste-aktie-top-krytowaehrung-20426830.html?feed=directrssfeed", "pdf_media_type": null, "previously_used_for_development": null, "publication_at": "2026-10-28T11:28:00Z", "publisher": "DER AKTIONÄR", "screenshot_media_type": null, "source_retrieved_at": "2026-10-28T13:15:02.646343Z", "teaser_text": "   Die Korrektur bei KI-Aktien und im Kryptosektor scheint überwunden. Bevor die Kurse zu schnell wieder steigen, was durchaus sehr wahrscheinlich ist, können jetzt noch die tiefen Kurse zum einstige genutzt werden. Bei einer Aktie und einer Kryptowährunf ist vom aktuellen Niveau aus sogar eine Verzehnfachung möglich.  ", "teaser_url": null}, "input_sha256": "ada264cd19d1d181d9e3ad6848b126879906529c69272566135cd065be080bd2", "source_key": "282b503c1ac7bf3c491f53168e801eea72b02073beda90487b35007257e219cc"}
```


<!-- TI-JOURNAL:43adea96df6b0b1ea8e643ca9dd796e52f3200be1ad5a0df783e7ddfa643b95d -->
### TI-282b503c1ac7bf3c491f – analysis – 2026-10-28T13:22:03.126362+00:00

```json
{"first_top3_unchanged": true, "ranking_sha256": "ba86a2ddccb06b96b78a97e28ef3ec14e98c21201b2b79ff162850230c94cc31", "report": {"candidates": [], "case_id": "TI-282b503c1ac7bf3c491f", "criteria": [{"category": "technologies", "clue_id": "32fd9a81e1f0afb839200192c3d90673cff8616011e7df5e6d9d49bb9c0df840", "confidence_class": "medium", "end": 78, "extraction_method": "deterministic_regex", "instrument_scope": "stock", "normalized": "ki", "page": null, "period": null, "polarity": "asserted", "quote": "KI", "reference_date": null, "requires_manual_review": true, "source_id": "teaser_text", "start": 76, "unit": null, "value": "KI"}], "headline": "Doppelter Verzehnfacher: Beste Aktie, Top-Krytowährung", "identification": {"label": "Nicht identifiziert", "requires_manual_review": true, "score_is_probability": false, "status": "not_identified"}, "limitations": ["fewer_than_five_countercandidates", "research_source_gaps", "insufficient_specific_primary_evidence"], "run_id": "c7bb9a8017c64d959f22005f056d6f54", "source_timing": [{"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T12:28:00+00:00", "retrieved_at": "2026-10-28T13:22:00.656947+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/aktien/doppelter-verzehnfacher-beste-aktie-top-krytowaehrung-20426830.html?feed=directrssfeed"}, {"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T12:33:00+00:00", "retrieved_at": "2026-10-28T13:22:01.195785+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/medien-it-technologie/vertiv-20426794.html?feed=directrssfeed"}, {"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T13:43:00+00:00", "retrieved_at": "2026-10-28T13:22:01.944275+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/mobilitaet-oel-energie/enphase-mit-duesteren-zahlen-solar-aktie-crasht-20426900.html?feed=directrssfeed"}, {"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T13:57:00+00:00", "retrieved_at": "2026-10-28T13:22:02.156459+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/aktien/siemens-energy-erhaelt-die-aktie-rueckenwind-von-ge-vernova-20426912.html?feed=directrssfeed"}, {"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T13:59:00+00:00", "retrieved_at": "2026-10-28T13:22:02.394984+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/gold-rohstoffe/biogen-ueberrascht-aktie-auf-2-jahreshoch-und-nun-20426945.html?feed=directrssfeed"}, {"availability_basis": "unknown", "availability_evidence": null, "availability_status": "uncertain", "content_revision_at": null, "eligibility": "after_cutoff", "event_at": null, "published_at": "2026-10-28T14:10:00+00:00", "retrieved_at": "2026-10-28T13:22:02.614001+00:00", "source_available_at": null, "url": "https://www.deraktionaer.de/artikel/pharma-biotech/biogen-20426885.html?feed=directrssfeed"}]}}
```


## Änderungsjournal – V3.1 (28.10.2026)

- Die 18 historischen Fälle und ursprünglichen Fehlprognosen bleiben erhalten.
- Neue Fälle, Erstprognosen und spätere Auflösungen werden als hashreferenzierte
  Erweiterungen angehängt. Scanner und spätere Registerfortschreibung sind getrennt.
- Der öffentliche RSS-Teaser von Alfred Maydorn wurde als unbewertete retrospektive
  Recherche protokolliert, nicht als HEBELTRADER-Blindtest oder erfolgreicher Treffer.
- Historische Verfügbarkeit benötigt eine beobachtete Originalversion oder einen
  inhaltsgebundenen Archivbeleg; Publikation allein ist keine Verfügbarkeitsgarantie.


<!-- TI-JOURNAL:cedca79e86b0b1489c48bb084b7b646968d77b7fd7f9f3364882b7c8437a8d7c -->
### TI-ffbb614727fb96f052ea – intake – 2026-10-28T14:02:39.768044+00:00

```json
{"content_key": "670bc65634c1960c37967ab404d79f87114e6d66c976daf830864c3b68d39a26", "input": {"author": "Rudolf Wittmer", "evaluation_class": "retrospective", "headline": "Achtung, Kursexplosion voraus – KI-Boom trifft Ölgeschäft!", "issue": "198/26", "original_source_url": "https://www.boersenmedien.de/produkt/hebeltrader/hebeltrader-19826-5097.html", "previously_used_for_development": null, "publication_at": null, "publication_date": "2026-10-26", "publication_time_unknown": true, "publisher": "Börsenmedien / DER AKTIONÄR", "research_started_before_journal_intake": true, "source_retrieved_at": "2026-10-28T13:57:53.726403+00:00", "teaser_text": "Ein Konzern, der sich seit Jahrzehnten im Hintergrund der Förderung bewegt, hat sich neu erfunden und sitzt jetzt im Rechenzentrum. Die Spuren führen zu KI-Kühltechnik, zu einer Digitalsparte mit wiederkehrenden Milliardenerlösen und zu einem Quartalsbericht, der selbst Skeptiker verstummen ließ. Die Charttechnik zeigt ein eindeutiges Muster: Nach der Korrektur hat die Aktie die 200-Tage-Linie erneut verteidigt. Wer hier den Hebel ansetzt, hat ein Motiv: Der Call-Optionsschein könnte bei Erreichen des ersten Kursziels um bis zu 421 Prozent zulegen, bei einer Fortsetzung der Rally sogar um 1.464 Prozent.\n\nDie komplette Akte mit Einstieg, Kurszielen, Stopps und Handelsregeln gibt es nur in der aktuellen Analyse. Jetzt zugreifen!"}, "input_sha256": "f069feb3247800511a2b7d7232db28d5b310e9fc2cfa357ec0b18e8cf2bebc5b", "source_key": "ffbb614727fb96f052ea0fefee1e26a4674139ebf1b1490d02b0ce692654f5b0"}
```


<!-- TI-JOURNAL:74c74015bfd54e88a7d3bd07f13158ecdc382c5cfd2afd5d9d6e2fc8aaf1fa98 -->
### TI-ffbb614727fb96f052ea – analysis – 2026-10-28T14:02:39.771806+00:00

```json
{"first_top3_unchanged": true, "ranking_sha256": "ce5dabf44e707bc1179ff70d554a555a85a59ca93828f9c8f873a703d5767dd6", "report": {"candidates": [{"asset_id": "SLB", "counterarguments": ["Kelvion closing expected H1 2027, not already owned at teaser date.", "Digital Q3 revenue -1% sequentially; GAAP EPS -6% sequentially.", "No exact publication time or historically authenticated content snapshot; chart and call unknown."], "evidence_matrix": [{"clue": "Foerderungsnahes Geschaeft", "historical_version_verified": false, "note": "Reservoir Performance, Well Construction and Production Systems in issuer results.", "score_points": 4, "sources": ["https://investorcenter.slb.com/news-releases/news-release-details/slb-announces-third-quarter-2026-results"], "status": "confirmed"}, {"clue": "KI-Kuehltechnik / Rechenzentren", "historical_version_verified": false, "note": "Existing Data Center Solutions; Kelvion thermal-management acquisition agreed August 31, not yet closed.", "score_points": 4, "sources": ["https://investorcenter.slb.com/news-releases/news-release-details/slb-acquire-kelvion-expanding-its-role-across-data-center", "https://investorcenter.slb.com/news-releases/news-release-details/slb-announces-third-quarter-2026-results"], "status": "confirmed"}, {"clue": "Digitalsparte mit wiederkehrenden Milliardenerloesen", "historical_version_verified": false, "note": "Digital annualized recurring revenue USD 1.04bn at September 30, 2026; not total segment revenue.", "score_points": 4, "sources": ["https://investorcenter.slb.com/news-releases/news-release-details/slb-announces-third-quarter-2026-results"], "status": "confirmed"}, {"clue": "Quartalsbericht ueberraschte Skeptiker", "historical_version_verified": false, "note": "Promotional claim; no dated consensus comparison.", "score_points": 0, "sources": [], "status": "unknown"}, {"clue": "200-session moving-average defense", "historical_version_verified": false, "note": "No verified price series or publication-time snapshot.", "score_points": 0, "sources": [], "status": "unknown"}], "evidence_score": 12, "identity": {"isin": null, "name": "SLB (frueher Schlumberger)", "ticker": "SLB"}, "sources": ["https://investorcenter.slb.com/news-releases/news-release-details/slb-acquire-kelvion-expanding-its-role-across-data-center", "https://investorcenter.slb.com/news-releases/news-release-details/slb-announces-third-quarter-2026-results"]}, {"asset_id": "Schneider Electric", "counterarguments": ["No equally specific oilfield-service transformation evidence.", "ARR growth is not proof of absolute recurring billions; do not confuse total software sales with ARR."], "evidence_matrix": [{"clue": "Foerderungsnahes Geschaeft", "historical_version_verified": false, "note": "Energy & Chemicals end markets do not establish the described oilfield-service heritage.", "score_points": 0, "sources": ["https://www.se.com/ww/en/assets/pdf/release-hy-results-2026"], "status": "unknown"}, {"clue": "KI-Kuehltechnik / Rechenzentren", "historical_version_verified": false, "note": "75% Motivair controlling acquisition closed February 28, 2025; direct liquid cooling.", "score_points": 4, "sources": ["https://www.se.com/ww/en/assets/564/document/506659/Schneider%20Electric-completes-acquisition-of-Motivair-Corporation.pdf"], "status": "confirmed"}, {"clue": "Digitalsparte mit wiederkehrenden Milliardenerloesen", "historical_version_verified": false, "note": "AVEVA recurring software and ARR +11% established; absolute billion ARR not verified in inspected source.", "score_points": 2, "sources": ["https://www.se.com/ww/en/assets/pdf/release-hy-results-2026"], "status": "unknown"}, {"clue": "Quartalsbericht ueberraschte Skeptiker", "historical_version_verified": false, "note": "Promotional claim; no dated consensus comparison.", "score_points": 0, "sources": [], "status": "unknown"}, {"clue": "200-session moving-average defense", "historical_version_verified": false, "note": "No verified price series or publication-time snapshot.", "score_points": 0, "sources": [], "status": "unknown"}], "evidence_score": 6, "identity": {"isin": null, "name": "Schneider Electric", "ticker": null}, "sources": ["https://www.se.com/ww/en/assets/564/document/506659/Schneider%20Electric-completes-acquisition-of-Motivair-Corporation.pdf", "https://www.se.com/ww/en/assets/pdf/release-hy-results-2026"]}, {"asset_id": "EMR", "counterarguments": ["Cooling source describes instrumentation rather than the same cooling-systems transformation.", "ACV, backlog and ARR are different metrics; no unsupported billion comparison."], "evidence_matrix": [{"clue": "Foerderungsnahes Geschaeft", "historical_version_verified": false, "note": "Aspen Geolog supports upstream exploration; industrial supplier, less direct than SLB.", "score_points": 2, "sources": ["https://www.emerson.com/en/corporate/news/2026/emerson-selected-by-logtek-as-to-accelerate-upstream-exploration"], "status": "confirmed"}, {"clue": "KI-Kuehltechnik / Rechenzentren", "historical_version_verified": false, "note": "October 8 Rosemount flow measurement for hydronic cooling, not an equivalent full thermal-management business.", "score_points": 2, "sources": ["https://www.emerson.com/en/corporate/news/2026/emersons-new-flow-measurement-improves-data-center-reliability"], "status": "confirmed"}, {"clue": "Digitalsparte mit wiederkehrenden Milliardenerloesen", "historical_version_verified": false, "note": "AspenTech recurring contract portfolio is documented; an absolute billion ARR figure is not verified.", "score_points": 1, "sources": ["https://ir.emerson.com/_assets/_39b9c4b55c1314921bb642cd27956a1b/emerson/db/938/10242/presentation/Emerson+2026+Q3+Earnings+Presentation.pdf"], "status": "unknown"}, {"clue": "Quartalsbericht ueberraschte Skeptiker", "historical_version_verified": false, "note": "Promotional claim; no dated consensus comparison.", "score_points": 0, "sources": [], "status": "unknown"}, {"clue": "200-session moving-average defense", "historical_version_verified": false, "note": "No verified price series or publication-time snapshot.", "score_points": 0, "sources": [], "status": "unknown"}], "evidence_score": 5, "identity": {"isin": null, "name": "Emerson", "ticker": "EMR"}, "sources": ["https://ir.emerson.com/_assets/_39b9c4b55c1314921bb642cd27956a1b/emerson/db/938/10242/presentation/Emerson+2026+Q3+Earnings+Presentation.pdf", "https://www.emerson.com/en/corporate/news/2026/emerson-selected-by-logtek-as-to-accelerate-upstream-exploration", "https://www.emerson.com/en/corporate/news/2026/emersons-new-flow-measurement-improves-data-center-reliability"]}], "case_id": "TI-ffbb614727fb96f052ea", "criteria": null, "headline": "Achtung, Kursexplosion voraus – KI-Boom trifft Ölgeschäft!", "identification": {"label": "SLB ist die staerkste belegte Hypothese; Newsletter-Aufloesung unbestaetigt", "score_is_probability": false, "status": "not_identified"}, "limitations": ["Exact teaser publication time unknown.", "Sources first accessed today; historical versions not authenticated.", "No price series verified for 200-session average.", "No original call WKN or product data; promotional returns not used.", "Assistant-led research, not proof of autonomous scanner identification.", "No later resolution supplied; no hit rate."], "run_id": "hebeltrader-19826-initial", "source_timing": null}}
```


<!-- TI-JOURNAL:9321b53dbd1483a872b6fb55462402bb26b00cc64bf5e9e1842931eac8e3e8ed -->
### TI-ffbb614727fb96f052ea – resolution – 2026-10-28T14:51:46.306710+00:00

```json
{"algorithm_change": "Keine fallbezogene Gewinnerregel einbauen. Kombination konkreter Unternehmensereignisse vor generischen KI-/Chartmerkmalen beibehalten; nach Nutzeraufloesung als Entwicklungsfall behandeln.", "asset_id": "SLB", "basis": "primary_source", "call_wkn": "VY95PV", "case_status": "bestaetigt", "confirmed_at": "2026-10-28T14:51:46.305050+00:00", "correct_rank": 1, "error_analysis": "Erstprognose SLB auf Rang 1 durch die erst spaeter bereitgestellte PDF bestaetigt. Foerdergeschaeft, Rechenzentren/Kuehltechnik, geplante Kelvion-Uebernahme und Digitalsparte stimmen ueberein. Kein falscher Basiswert. Call-WKN war vor der Aufloesung korrekt als unbekannt markiert. Kein Beleg einer vollautonomen Scanner-Identifikation oder kalibrierten Trefferquote.", "name": "SLB (frueher Schlumberger)", "original_call_status": "original_reported_by_source", "original_sha256": "4a4f6537957e5e7f5253418e67234bb092b6dff6eb274d59220eaaafbc728292", "prediction_outcome": "confirmed", "product_verification": "not_verified", "source": "Vom Nutzer bereitgestellte Herausgeber-PDF Hebeltrader_2026-198.pdf; Ausgabe 198/2026 vom 26.10.2026; Seiten 1-3; PDF-SHA256 fca10fe1a464f5cfca21aca6e3a6c153e71dc575345d665e862b546bc8d926c4"}
```


## HT-001 – zusätzlicher Originalreport-Beleg (28.10.2026)

Nachträglich vom Nutzer bereitgestellt: HEBELTRADER **200/2026 vom 28.10.2026**, sechs
Seiten. Seite 1 nennt **Analog Devices (ADI)** und den Original-Call **MN84GA**.
PDF-SHA256: `e8f1365890bf789b119713174e67aa1cd9a147bda870f8f4ecccb77c824ad1c2`.

Die vorhandene Nutzerauflösung ist damit durch den bereitgestellten Herausgeberreport
belegt. Der ursprüngliche Tipp **Lattice Semiconductor (LSCC) bleibt falsch**; die
unbegründete 95-%-Angabe bleibt als Fehler dokumentiert. Kein neuer Blindtest oder Treffer.

Der Report beschreibt Empower Semiconductor und einen **geplanten** Zukauf von Alif
Semiconductor. Diese jetzt aus der Auflösung bekannten Details beweisen nicht, dass sie
im vollständigen ursprünglichen anonymisierten Teaser verfügbar waren. Sie dürfen nicht
nachträglich in dessen Blindtest-Eingabe übernommen werden. Die komplette ursprüngliche
Top-3-Liste bleibt unbekannt. Emittentenprüfung zu MN84GA bleibt offen.

Änderungsjournal: Ergänzender Quellenbeleg zu HT-001; keine Änderung des alten
Registereintrags oder der historischen Fehlwertung.
Nachweis: [maschinenlesbare Quellenbestätigung](hebeltrader-20026-source-confirmation.json).


## Änderungsjournal – strukturierte 18-Fall-Referenzsammlung (28.10.2026)

- Alle 18 Überschriften gemäß ergänztem Nutzerauftrag übernommen. Historische IDs behalten,
  Nutzernummerierung separat gespeichert. Die vorherige Tabelle ist als datierter Snapshot
  erhalten; aktuelle Tabelle ohne die bisherige Leerzeile innerhalb der 18 Datenzeilen.
- Neu konkretisierte Ersttipps ergänzt: UnitedHealth → Zurich, Zebra → Danaher,
  Oracle → SAP und Thales → Leonardo. Frühere Fehler und falsche 95-%-Angabe bleiben erhalten.
- Daten/Ausgaben nur soweit angegeben. JPM-/JNJ-Auflösungsdaten nicht als Publikation
  übernehmen; Thales-Datierung ausdrücklich als unbestätigte frühere Übersichtsangabe markieren.
- Williams: tatsächliche Aktie, tatsächlicher Ticker und Call-WKN null. WMB ist nur Verdacht.
- **Ein** vollständiger Originalteaser liegt jetzt vor: der vom Nutzer übermittelte
  ADI-Text in der strukturierten Referenzsammlung. Die übrigen 17 Volltexte fehlen weiterhin.
- Der ADI-Teaser nennt Zukäufe und Geschäftsfelder, aber **nicht** Empower oder Alif.
  Diese Namen stammen aus der Auflösung und dürfen nicht in den Blind-Input kopiert werden.
- Historische 60/55/95 % nur als unkalibrierte damalige Aussagen archiviert. Keine neue
  Wahrscheinlichkeit oder unabhängige Erfolgsquote. Die 10/7/1-Bilanz bleibt Nutzerhistorie.
- JSON-Export und Evaluator sind getrennt. Der eigentliche Scanner bekommt keine
  Referenz-/Lösungsdatei, historischen Ersttipps, WKNs oder Fehleranalysen.

### Änderungsjournal 28.10.2026 – öffentliche Auswahlstrategie

Ergänzung, keine Änderung historischer Fallprognosen: Die öffentliche HEBELTRADER-Shopseite
und die Deere-Leseprobe zeigen die Bedeutung von Unternehmenskennzahlen und Peer-Vergleich.
Die Rechercheplanung nutzt nun gezielte Ereignis-/Finanzfragen und aktive Wettbewerbersuche
vor der Falsifikation. Operativer und freier Cashflow werden in Suchfragen unterschieden;
Übernahmegerüchte bleiben Gerüchte. Charttechnik dient nur als ergänzender Suchhinweis,
Werberenditen weiterhin nicht als Aktienbeweis. Keine Herausgeber-Erfolgszahl gilt als eigene
Trefferquote. Details und Quellenkritik: [Strategieübernahme](hebeltrader-publisher-strategy.md).
Die 18 historischen Fallzuordnungen bleiben unverändert.

### Änderungsjournal 29.10.2026 – echte Such-/KI-Anbindung

Ergänzung ohne Änderung historischer Erstprognosen: Tavily-URL-Suche und OpenAI-Auswertung
werden optional an den bestehenden Downloader und die Kandidatenprüfung angeschlossen.
KI-Befunde brauchen wörtliche Zitate, bleiben vorläufig und unterliegen dem Zeitfilter.
Auch eine allein durch KI ergänzte Identität erlaubt keine automatische Bestätigung.
Keine bekannten Lösungen oder WKNs gelangen in die KI-Planung. Budget und Freigabe bleiben
separat kontrolliert; ohne API-Zugänge ist die Live-Abnahme offen. Details:
[Such-/KI-Anbindung](teaser-search-ai.md).


## Neuer Fall HT-20226 – Erstprognose vom 30.10.2026

- Originalüberschrift: „Vom Tief zum Triumph: Die Comeback-Story des Jahres!“
- Nutzer lieferte den Teasertext einschließlich 1.311 % Call-Werbepotenzial; letzter Satz abgebrochen. Öffentlicher Suchindex ordnet denselben Text Rudolf Wittmer, HEBELTRADER 202/26, Erscheinungsdatum 30.10.2026 zu. Direkter Shopabruf war nicht verfügbar. Keine genaue Publikationsuhrzeit belegt.
- Quelle: https://www.boersenmedien.de/produkt/hebeltrader/hebeltrader-20226-5112.html
- **Eingefrorene assistentengestützte Erstprognose:** 1. Deutsche Bank, 2. Commerzbank, 3. UBS. Rang 2/3 sind deutlich schwächere Vergleichskandidaten, keine gleichwertigen Identifikationen.
- Favorit: Deutsche Bank AG, DBK, Aktien-WKN 514000, ISIN DE0005140008.
- Status: starke, primärquellenbasierte Hypothese; Herausgeberauflösung noch nicht vorhanden. Original-Call-WKN unbekannt, Produktparameter ungeprüft.
- Kein autonomer Scannerlauf und kein bestätigter unabhängiger Blindtest. Keine Prozent-Konfidenz. Keine Änderung der historischen 18-Fall-Bilanz.

### Kernhinweise und aktive Gegenprüfung

| Kriterium | Deutsche Bank | Commerzbank | UBS |
|---|---|---|---|
| Drittes Rekordquartal in Folge | Explizit in Unternehmensmeldung vom 28.10.2026 | Rekord-Halbjahr belegt; Q3 erst für 05.11.2026 terminiert; kein passender aktueller Nachweis | Q3-Nettogewinn 2,690 Mrd. USD nach 2,800 Mrd. in Q2; konkrete Dreier-Rekordformulierung nicht belegt |
| Ertragswachstum | Q3 +4 % auf 8,3 Mrd. EUR | H1 +7 % auf 6,5 Mrd. EUR | Q3 13,350 Mrd. USD nach 12,760 Mrd. im Vorjahr |
| Kapital/Ausschüttungen | CET1 14,0 %, Ausschüttungsquote 60 %; 1,5 Mrd. EUR Rückkäufe 2026 bereits abgeschlossen | CET1 14,4 %, geplanter Rückkauf bis 1,2 Mrd. EUR laut Augustmeldung | CET1 14,7 %, Rückkäufe/Dividendenwachstum vorgesehen |
| 200-Tage-Linie | Sekundärdaten melden Kreuzung am 29.10.; Brokeranalyse vom 29.10. beschreibt Schluss vom 28.10. noch darunter. Keine eigene Neuberechnung | Nicht verifiziert | Nicht verifiziert |
| Kurszielanhebungen | UBS 37→38 EUR, Originalstudie laut dpa vom 29.10.; Citi 31,70→32,80 EUR sekundär berichtet | Keine passende Serie in dieser Prüfung belegt | Keine passende Serie in dieser Prüfung belegt |

Zusätzlich aktiv geprüfte Gegenkandidaten:
- Barclays: Q3-Bericht mit CET1 14,2 %, neuem Rückkauf bis 500 Mio. GBP und wachsendem Ergebnis. Exakte dreimalige Rekordserie nicht belegt.
- HSBC: Q3-Vorsteuergewinn 9,6 Mrd. USD berichtet; 10,0 Mrd. ohne Sondereffekte. Nicht vermischen. CET1 13,9 %, gegenüber Q2 um 0,2 Prozentpunkte gesunken: schwächerer Match zum Kapitalaufbau; kein Beleg der spezifischen Rekordserie.
- Citigroup: Q3-Nettogewinn 5,2 Mrd. USD, Erträge +8 % zum Vorjahr, CET1 12,8 % unverändert zum Vorquartal, Ausschüttungen 4,1 Mrd. USD. Keine genaue Dreier-Rekordserie belegt.

Falsifikation des Favoriten:
- „Rekord“ bezeichnet hier periodenspezifische Quartalsrekorde, nicht zwingend drei nacheinander absolut steigende Quartalsgewinne.
- „Ausschüttungen rücken näher“ ist unpräzise: Rückkäufe sind bei Deutsche Bank bereits erfolgt, nicht erstmals möglich.
- „Kapitalbasis so stark wie lange nicht“ ist durch CET1 14,0 % am oberen Zielrand gestützt, aber kein geprüfter historischer Höchststand.
- Chartinformationen hängen an Datum, Börsenplatz und Datenreihe; der Schluss vom 28.10. ist nicht gleich dem vom 29.10. Keine nachträgliche Chartbestätigung aus bloßer Teaserbehauptung.
- Nicht bei jeder Alternative ist ein Gegenbeweis belegt. Ein fehlender Nachweis der Rekordserie bleibt unbekannt und wird nicht als bewiesene Widerlegung ausgegeben.

### Quellen der Erstprüfung

Unternehmens-/Regulatorquellen:
- https://www.db.com/news/detail/20261028-deutsche-bank-veroeffentlicht-ergebnisse-zum-dritten-quartal-2026
- https://www.eqs-news.com/de/news/corporate/commerzbank-erzielt-rekordergebnis-im-ersten-halbjahr-2026-ausblick-bestatigt/acd38764-866f-4f6a-a428-5676272652a9_de
- https://investor-relations.commerzbank.com/de/quartalsergebnisse
- https://www.ubs.com/global/en/investor-relations/press-releases/overview-news-display-ndp/en-20261028-3q26-quarterly-result.html
- https://www.sec.gov/Archives/edgar/data/312069/000031206926000240/bplcq326resultsannouncement.htm
- https://www.hsbc.com/investors/results-and-announcements/all-reporting/3q-2026-quick-read
- https://www.sec.gov/Archives/edgar/data/831001/000110465926115323/c-ex99d1.htm

Ergänzende Chart-/Analystenquellen, keine fundamentalen Primärbelege:
- https://www.xtb.com/de/Marktanalysen/Trading-News/deutsche-bank-aktie-dax-spitzenreiter-nach-erholungsrallye-ein-signal-zum-aktien-kaufen
- https://www.finanzen.net/aktien/deutsche_bank-aktie
- https://www.wallstreet-online.de/nachricht/21609642-ubs-stuft-deutsche-bank-ag-buy
- https://goldesel.de/aktien/news/deutsche-bank-aktie-citi-hebt-kursziel-nach-starken-quartalszahlen-auf-3280-euro

Heute zugängliche Quellen sind keine authentifizierten historischen Inhaltsfassungen.
Die Recherche ist vor einer hier vorliegenden Herausgeberauflösung erfolgt, aber ohne
extern attestierten Freeze-Zeitpunkt und ohne vollständiges Rohdatenarchiv.

### Regression für spätere Implementierung

Periodenbezogene Quartalsrekorde nicht mit sequenziell steigendem Gewinn verwechseln;
Vorsteuer-/Nettogewinn und berichtet/bereinigt getrennt halten; Kapitalstärke nicht ohne
Zeitreihe als Rekord bestätigen; Chartdurchbruch am exakten Handelstag prüfen; bereits
abgeschlossene Rückkäufe von neuen Ankündigungen unterscheiden. Gewinnername und
Call-Werbepotenzial dürfen keine Produktions-Rankingregel werden. Diese Dokumentation
enthält Testanforderungen, keine neu ausgeführten Produkttests.


## Auflösung HT-20226 / HT-028 und Gesamtbilanz (30.10.2026)

**Nutzerbestätigung nach der Erstprognose:** „Es ist die Deutsche Bank.“
Damit ist der vorher dokumentierte Rang-1-Tipp Deutsche Bank richtig. Rangfolge
Deutsche Bank → Commerzbank → UBS bleibt unverändert. Bestätigungsart:
Nutzerauflösung, kein neu vorliegender Originalreport. Original-Call-WKN und
Produktparameter weiterhin unbekannt. Keine autonome Scanneridentifikation.

Allgemeine Lehren:
1. Seltene, überprüfbare Ergebnisfolgen („drittes Rekordquartal in Folge“) als
   Ereignisfingerabdruck in zeitnahen Unternehmensmeldungen suchen.
2. Periodenspezifische Rekorde von sequenziell steigenden absoluten Gewinnen
   unterscheiden; berichtet/bereinigt und Vorsteuer-/Nettogewinn nicht vermischen.
3. Ertragswachstum, Kapitalquote und Ausschüttungspläne gemeinsam prüfen.
   Allgemeine Comeback-/Chartwörter allein sind keine belastbare Identifikation.
4. Chartdurchbruch an Handelstag, Börsenplatz und Datenreihe binden. Bereits
   durchgeführte Rückkäufe nicht als erstmals bevorstehende Ausschüttung ausgeben.
5. Trotz starkem Ereignisfingerabdruck fünf Gegenkandidaten prüfen. Kein Gewinnername
   als feste Rankingregel; keine Prozentwahrscheinlichkeit ohne Kalibrierung.

### Registerabgleich und unveränderte Erstversuche

Der strukturierte Fall HT-019 (198/26) war noch ungelöst, obwohl weiter oben die
SLB-Erstprognose und spätere Originalreport-Bestätigung bereits dokumentiert sind.
Diese Nachführung ist **derselbe Fall**, kein zusätzlicher neuer Test:
SLB / VY95PV, Rang 1 richtig. Frühere strukturierte Werte sind in resolution_history
erhalten. Der neue Deutsche-Bank-Fall trägt die strukturierte ID HT-028; HT-20226
bleibt der Alias für die ursprüngliche Dokumentation. Keine neue Doppelzählung.

### Statistik mit getrennten Nennern

- Historische 18 Fälle unverändert: 10 richtig, 7 falsch, Williams ungelöst.
- Zusätzlich assistentengestützt bestätigt: SLB und Deutsche Bank, beide Rang 1 richtig.
- Vergleichbare Gesprächsbilanz: **20 Fälle = 12 richtig + 7 falsch + 1 ungelöst**.
  Aufgelöste Fälle: 12/19 = **63,2 %**; alle 20 Fälle: 12/20 = **60,0 %**.
- Synopsys / MN9WA9 separat: bekanntes Label, Rang 1 im Lauf, aber keine
  Identifikation freigegeben (not_identified). Kein ausgesprochener Treffer.
- Sieben weitere Referenzen ohne dokumentierten Ersttipp: BP, Constellation Energy,
  AbbVie, Eni, Adidas, Carrier Global, Thermo Fisher. Nicht als Treffer zählen.
- Insgesamt **28 unterschiedliche Referenzfälle**: 12 correct, 7 wrong,
  1 unresolved, 1 not_identified, 7 not_tested. Davon 21 Fälle mit dokumentiertem
  Versuch einschließlich Synopsys; 20 davon haben bekannte Auflösung.
  Einschließlich dieser Enthaltung: 12/20 = **60,0 %** Identifikationserfolg auf
  aufgelösten versuchten Fällen; 12/21 = **57,1 %** auf allen versuchten Fällen.
- Kein Zusammenwerfen mit dem ungelösten Maydorn-/Krypto-RSS-Fall; anderer Autor,
  anderer Gegenstand. Keine unabhängige Benchmarkquote oder statistisch
  nachgewiesene Qualitätssteigerung aus zwei zusätzlichen Treffern ableiten.

Quelle: aktuelle strukturierte Referenzsammlung, bereits protokollierte SLB-Auflösung,
Git-gespeicherte Deutsche-Bank-Erstprognose und anschließende Nutzerbestätigung.

Regressionen: tests/hebeltrader/test_reference_resolution_summary.py prüft
unveränderte historische Bilanz, getrennte Enthaltung/Referenzfälle, Originalrangfolge,
unbekannte Call-WKN und Ausschluss von Auflösungsfeldern aus Scannerinputs.
Drei Tests mit unittest lokal bestanden. pytest ist in der aktuellen Prüfumgebung
nicht installiert; die gesamte Produktsuite wurde nicht ausgeführt. Der bestehende
Referenztest wurde auf 28 Einträge und den nachgeführten SLB-Status angepasst.
