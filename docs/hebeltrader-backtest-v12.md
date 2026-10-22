# Backtesting V1.2: getrennte Forschungs- und Verfügbarkeitsprüfung

V1.2 ergänzt die bestehende Offline-Analyse um zwei ausdrücklich getrennte
Analysemodi. Die Methodenversion lautet `hebel-stock-ohlc-v1.2`. Es gibt
keine Datenbankmigration und keine Änderung gespeicherter Verfügbarkeit,
Empfehlungen, Reviews oder Outcomes. Die Ausführung bleibt rein lesend.

## Moduswahl

```bash
# Standard: bisherige strenge Availability-Prüfung
python -m scanner.hebeltrader backtest --analysis-mode verified \
  --bars-dir /input/market --map /input/mapping.json --rules /input/rules.json \
  --as-of 2026-10-22T00:00:00+02:00 --output /reports/verified-v12.json

# Ausdrücklich hypothetische Forschung auf Grundlage des Publikationsdatums
python -m scanner.hebeltrader backtest --analysis-mode research \
  --bars-dir /input/market --map /input/mapping.json --rules /input/rules.json \
  --as-of 2026-10-22T00:00:00+02:00 --output /reports/research-v12.json
```

`verified` bleibt der Default, auch beim Python-Aufruf `build_report(...)`.
Seine bisherige Prüfung bleibt erhalten: ohne belegten timezone-aware
Verfügbarkeitszeitpunkt und Quellennachweis bleibt eine Empfehlung
`unknown / unverified_availability`. Ausgewählte Revisionen, Reviewstatus,
Publikationsgrenze und Stichtag werden wie zuvor geprüft. „Verified“ bezieht
sich auf diese Quelleingangskriterien, niemals auf echte Orderausführung.

`research` ersetzt ausschließlich den fehlenden Availability-Nachweis durch
eine dokumentierte Modellannahme. Voraussetzung ist ein belegtes
Publikationsdatum: ein passender Originalheader in `metadata_evidence`, der
auf der angegebenen gespeicherten PDF-Seite steht und genau zum gespeicherten
Datum passt. Metadatenkonflikte, ungültige Daten, Dateinamen oder Archivordner
sind kein Ersatz für diesen Beleg. Der Original-SHA-Check bleibt erhalten.

## Frühestmögliche modellierte Sitzung

Der gesamte Publikationstag wird ausgeschlossen. Der exklusive Modell-Cutoff
ist das spätere Ende dieses Datums in Europe/Berlin (Publikationszone) und in
der expliziten Börsenzeitzone aus dem Mapping. Damit wird weder ein später
veröffentlichter Text am bereits vergangenen Tages-Open gehandelt noch ein
lokaler Börsentag irrtümlich als Folgetag eingeordnet. Zeitzonen und konkrete
Grenze stehen im Audit. Bei weit auseinanderliegenden Zeitzonen kann diese
bewusst konservative Regel eine zusätzliche Sitzung ausschließen.

Aus dem gelieferten Handelskalender wird die erste Sitzung mit Open nach
dieser Grenze verwendet, deren gesamtes OHLCV-Intervall bis `--as-of`
abgeschlossen ist. Der Open ist ein hypothetischer Modelleinstieg. Eine exakt
um Mitternacht des Folgetags öffnende Sitzung ist zulässig; eine während des
Publikationstags bereits geöffnete Overnight-Sitzung ist es nicht.

- Freitag, Samstag oder Sonntag: nächste tatsächlich gelistete Kalendersitzung,
  typischerweise Montag; bei einem Feiertag entsprechend später.
- Intraday-Veröffentlichung: im Forschungsmodus kein Open des Publikationstags.
- Liegt zusätzlich ein belegter späterer Verfügbarkeitszeitpunkt vor, wird
  dieser als weitere Untergrenze berücksichtigt, niemals vorgezogen.
- Ist die erste mögliche Sitzung am Stichtag noch offen, gibt es keinen
  Einstieg aus deren High/Low/Close. Spätere Bars werden nicht verwendet.
- Fehlt eine laut Kalender erforderliche Bar, bleibt die Auswertung unknown;
  der Einstieg wandert nicht stillschweigend auf eine spätere vorhandene Bar.
- Zukünftige Kurse, Actions und nach dem Stichtag öffnende Kalendereinträge
  beeinflussen kein früheres Ergebnis. Ein völlig unlesbarer Kalender-Open
  bleibt ein Datenfehler, weil seine zeitliche Zuordnung unmöglich ist.

Die Annahme beweist **keine tatsächliche historische Verfügbarkeit** des PDFs.
Bekannte Widersprüche, zukünftige belegte Verfügbarkeit, abgelehnte oder
ersetzte Dokumente und ungeklärte Revisionen werden nicht durch research
umgangen. Historische Identitäts-, Coverage-, Kalender-, Währungs-,
Corporate-Action- und Regelprüfungen bleiben ebenfalls erforderlich.

## Getrennte Auditfelder

| Feld | Bedeutung |
|---|---|
| `analysis_mode` | `verified` oder `research`, im Gesamtreport und jeder Zeile |
| `mode` | Unverändert `read_only`; unabhängig vom Analysemodus |
| `available_at`, `availability_evidence` | Unveränderte gespeicherte Angaben; keine erfundene Availability |
| `availability_status` | `verified`, `unverified` oder `assumed_from_publication_date` |
| `publication_evidence` | Passender Originalheader mit Seite und Extraktionsregel im Forschungsmodus |
| `publication_timezone`, `calendar_timezone` | Grundlage der konservativen Tagesgrenzen |
| `entry_cutoff_exclusive`, `cutoff_basis` | Hypothetische Untergrenze und deren Herkunft; keine Verfügbarkeitsbehauptung |
| `modeled_entry_at` | Erste geeignete vollständige Sitzung bei validierter Marktdatenabdeckung; kein realer Fill |
| `hypothetical` | Immer true: auch verifizierte Quellen machen OHLC nicht zu Orderbelegen |
| `training_eligible` | Immer false, insbesondere bei sämtlichen Forschungszeilen |
| `source_verified` | Im Forschungsmodus immer false; im strengen Modus bisherige Quellenbedingungen |

Modus und Cutoff-Audit gehen in `input_sha256` ein. Beide Modi können deshalb
nicht unbemerkt als dieselbe Auswertung behandelt werden. Alle neuen Felder
stehen auch im CSV. Reports eines Laufs mischen keine Modi; getrennte
Ausgabepfade verwenden. Modellierte Bruttorenditen bleiben separat, reale
Renditen und Erfolgsquote bleiben null; Derivate `derivative_unverified`.

Bei unbekannten Regeln oder Marktdaten kann ein Forschungsbericht weiterhin
118 unknown-Ergebnisse enthalten. V1.2 beseitigt dann den Availability-Block,
erfindet aber keine Quellen oder Ausstiegsregeln. Ein 118-Zeilen-Test prüft
explizit den Übergang von unverified_availability zu missing_documented_rules.

## Beispiele, Tests und Betrieb

[Verifizierter Beispielbericht](examples/hebel-backtest/report.json) und
[Forschungsbericht](examples/hebel-backtest/research-report.json), jeweils auch
als CSV im selben Ordner, sind vollständig synthetisch. Im Forschungsbeispiel
fehlt die Availability absichtlich. Der erste Folgetags-Open liegt bereits am
Ziel 1: der bestehende Entry-Range-Guard ergibt deshalb unknown, statt einen
Erfolg zu erfinden. `modeled_entry_at` dokumentiert die Kandidatensitzung auch
bei einem danach abgewiesenen Einstieg. Erfolgreich modellierbare Folge-Opens
sowie Wochenenden/Feiertage werden separat automatisiert getestet.

Reproduktion, Provider-Schema und späterer optionaler Containeraufruf:
[Backtesting-Dokumentation](hebeltrader-backtest-v1.md). Ergänzend sind
Publikationstag, Intraday-Veröffentlichung, verspätete belegte Availability,
Wochenenden, Feiertage, Sommerzeit, Börsenzeitzonen, Overnight-Sitzungen,
unvollständige Sessions, fehlende Bars, zukünftige Daten und Kalender,
getrennte CSV-/JSON-Audits und unveränderte Standardprüfung getestet.

Kein Deployment und keine Hetzner-Kommandos. Keine neue Migration erforderlich.
Ein späterer Betreiberlauf kann den bestehenden Analysebefehl mit
`--analysis-mode research` ergänzen; kein Scheduler oder Service muss dafür
aktiviert werden. Bestehende Importdaten bleiben unverändert.

## Ausgeführte Prüfungen

22.10.2026: **189 Tests erfolgreich**, einschließlich wegwerfbarem PostgreSQL
17.6 und READ-ONLY-/118-Zeilen-Tests für beide Modi. Ruff, Formatprüfung,
`git diff --check` und beide Compose-Konfigurationen erfolgreich. Docker-Image
gebaut; CLI- und Migrations-Smokechecks erfolgen ausschließlich lokal.
Beispielberichte beider Modi wurden bytegleich reproduziert. Unabhängiges
Review ohne verbleibende blockierende Befunde. Keine Hetzner-Änderungen.
