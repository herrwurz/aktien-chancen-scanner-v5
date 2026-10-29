# Öffentliche HEBELTRADER-Strategie für den Detektiv nutzen

Stand: 28.10.2026. Quelle: [öffentliche Shopseite](https://www.boersenmedien.de/shop/hebeltrader.html)
und die dort rechtmäßig bereitgestellte [Leseprobe 04/2026](https://cdn.boersenmedien.com/public/4576d341-2a42-407f-a1ed-e14469510c48/Hebeltrader_2026-04_LESEPROBE.pdf).
Die Prüfung enthält keine kostenpflichtigen Inhalte und keinen Zugang zu einem Abo.

## Was übernommen wurde

Die Publikation beschreibt Chartprüfung, Fundamentaldaten und anschließende Derivateauswahl.
Für die Identifikation einer anonymisierten Aktie bleiben konkrete Unternehmensereignisse
unterscheidungskräftiger als allgemeine Chartformulierungen. Der Detektiv übernimmt deshalb:

- Gezielte, nur vom Eingabetext abgeleitete Suche nach Übernahmen, Partnerschaften,
  Großaufträgen, Prognoseanhebungen, Zulassungen und Aktienrückkäufen.
- Quartalskennzahlen, Gewinn je Aktie, Analystenerwartungen und wiederkehrende Erlöse
  erhalten eigene Suchanfragen. Analystenbewertungen werden auch ohne Kennzahlen gesucht.
- Operativer Cashflow wird nicht mehr pauschal als Free Cashflow gesucht. Ein unspezifischer
  Cashflow-Hinweis bleibt unspezifisch; nur ausdrückliche FCF-Hinweise erzeugen FCF-Suchen.
- Nach erster Kandidatenrecherche werden die bis zu drei Führenden jeweils nach
  Wettbewerbern und Peer-Group-Unterlagen durchsucht. Danach werden alle Kandidaten erneut
  mit der bestehenden einheitlichen Evidenzmatrix verglichen. Die anschließende Falsifikation
  richtet sich gegen die dann führenden Kandidaten.
- Nur wenn die Eingabe tatsächlich die 200-Tage-Linie nennt, entsteht die entsprechende
  technische Suchanfrage. Es wird kein aktueller Chartwert erfunden oder berechnet.
- Übernahmespekulationen werden bei der Suche ausdrücklich als Gerücht behandelt.

Die neue `peer_comparison`-Sektion des JSON-Berichts archiviert Suchanfragen, Status und
Kandidatenzahl vor/nach der Suche. Die Browseroberfläche zeigt diese Informationen an.
Eine Peer-Suchanfrage beweist allein weder eine tatsächliche Wettbewerberbeziehung noch
eine erfolgreiche Quellenprüfung. Offline steht ausdrücklich `not_performed_offline`.

Es gibt höchstens acht initiale Suchanfragen und bis zu drei Peer-Suchanfragen. Alle
verwenden dasselbe bestehende öffentliche Quellen-/Requestbudget. Quellenfehler und
Budgetüberschreitungen werden weiterhin protokolliert und verhindern eine sichere
Identifikation. Es wird kein kostenpflichtiger Anbieter eingeschaltet.

## Was unverändert bleibt

Mindestens fünf belegte Gegenkandidaten, ausreichend spezifische zeitgerechte Primärbelege,
Instrumentidentifikation und die vorhandenen Falsifikationsschranken bleiben erforderlich.
Fehlende Belege werden weder durch Chartähnlichkeit noch durch ein Renditeversprechen ersetzt.
Derivate kommen erst nach gesicherter Aktienidentifikation. Keine Orders oder neuen
Kaufsignal-/Produktiv-Worker werden hinzugefügt.

Keine bekannten Lösungsnamen aus der Shopseite oder den 18 Referenzfällen werden als
Kandidatenliste eingebaut. Derivative WKNs und beworbene Prozentwerte sind keine Suchschlüssel
für den unbekannten Basiswert. Die historische 18er-Sammlung und ihre ursprünglichen
Fehlprognosen wurden nicht verändert.

## Tatsächliche Prüfung und Grenzen

Die reale öffentliche Deere-Leseprobe wurde eingelesen und zur Query-Prüfung verwendet:
Die Suche erhält den dort genannten operativen Cashflow als operativen Cashflow.
Das ist ein bekannter, bereits aufgelöster Entwicklungsfall, kein Blindtest und kein
Nachweis erfolgreicher autonomer Aktienidentifikation.

[Maschinenlesbarer Quellen-/Prüfnachweis](hebeltrader-publisher-strategy-check.json) mit
SHA-256 der gelesenen Dokumente und tatsächlich erzeugten Suchanfragen ist beigefügt.
Keine Gewinne oder Erfolgsquoten werden aus Herausgeberwerbung übernommen.

Die Quelle enthält Datumswidersprüche: Shopüberschrift nennt 2025-Beispiele, während
Empfehlungen im Text aus 2026 stammen; die PDF-Kursfußnote nennt 12.01.2025 statt des
Ausgabedatums 12.01.2026. Diese Angaben sind nicht als historisch verifizierte
Verfügbarkeitszeit oder aktuelle Kurse verwendbar.

Die Regressionstests prüfen Ereignissuche, den fehlenden Namens-Leak, Gerüchte,
Cashflow-Unterscheidung, technische Hinweise und das tatsächliche Hinzukommen weiterer
Kandidaten über Peer-Suche. Diese Kontrolltests nutzen synthetische Quellenpakete und
messen keine neue Trefferquote. Neue unabhängig aufgelöste Blindtests in dieser Änderung: 0.

Die öffentliche Websuche hat weiterhin die dokumentierten Provider- und Quellenlücken.
Die Funktion kann daher trotz besserer Rechercheplanung ungelöst bleiben. Kein Deployment
auf Hetzner wurde vorgenommen; die laufende Anwendung verwendet die Änderung erst nach
bewusster Aktualisierung auf den geprüften Branch.

Abschlussprüfung: **778 lokale Tests bestanden, 8 PostgreSQL-Tests übersprungen**;
Ruff/Format und JavaScript-Syntax erfolgreich. Docker-Build und isolierter Query-Smoke
(Partnerschaft sowie operativer statt freier Cashflow) erfolgreich. Eine bestehende
Starlette/AnyIO-Deprecation-Warnung bleibt. Read-only Code-Review ohne relevante Befunde.
