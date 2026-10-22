# V1.4: Layout- und Regelregressionen am 118er-Originalbestand

Diese Weiterentwicklung enthält die vollständige V1.4-Datenaufbereitung und ergänzt
sie um die fünf gemeldeten Hetzner-Regressionsfälle. Keine produktive Verbindung,
Migration oder Änderung importierter Werte findet statt. Das bereits lokal
vorhandene V1.3-Inventar wurde über eine SQLite-mode=ro-Verbindung gelesen.

## Ursache und Korrekturvorschläge

Die Spalten liegen im Original richtig getrennt vor. Der bisherige Parser verwendet
aber die exakte Namensgleichheit und teils die Reihenfolge der Textzeilen statt
ihrer geometrischen Nachbarschaft. Der neue Assistent arbeitet separat vom
Importparser: Er verlangt eine explizite Aktienüberschrift, genau einen Basiswert
im betreffenden Abschnitt, passende Spaltenkoordinaten und eindeutige numerische
Tabellenzeilen. Mehrere Tabellen/Zeilen oder unbelegte Namensvarianten verhindern
eine Zuordnung. Keine unscharfe Namenssuche und keine fest hinterlegten Firmenaliase.

| Original-SHA-Präfix | Ursache | Belegter Vorschlag |
| --- | --- | --- |
| 0423a87f – E.ON, 08.09.2025 | WKN steht leicht oberhalb rechts vom Label | Aktien-WKN ENAG99, Seite 3 |
| 52e053b7 – Innodata, 06.02.2025 | „Kursziel 2 kann die zweite Hälfte Ihrer“ im späteren Fließtext entwertet die zuvor korrekt gelesene Tabellenzahl | Ziel 2 = 91,20 EUR, Seite 3 |
| 5cf16313 – Occidental Petroleum, 20.02.2026 | „Occidental“ im Aktienabschnitt passt nicht exakt zum vollständigen Namen | WKN 851921; Kurs 51,53 USD, Ziele 62,00/78,50 USD, Stopps 45,00/51,53 USD, Seite 3 |
| ca53f7e4 – Waste Management, 18.02.2026 | „Waste Mgmt“ wird nicht mit dem vollständigen Namen verbunden | WKN 893579; Kurs 235,22 USD, Ziele 269,00/316,00 USD, Stopps 220,00/235,22 USD, Seite 3 |
| e73f23ac – Meta, 07.05.2025 | WKN steht leicht oberhalb rechts vom Label | Aktien-WKN A1JWVX, Seite 3 |

Die Originale belegen auf Seite 1 ausdrücklich „Occidental Petroleum (kurz:
Occidental)“ beziehungsweise „Waste Management (kurz: Waste Mgmt)“. Diese Zitate
werden zusätzlich zur Tabellenüberschrift, Basiswertzeile und Feldzeile als
Zuordnungsbelege ausgegeben. Die WKN-Paarung bei E.ON/Meta verlangt genau einen
rechts liegenden, vertikal überlappenden Wert mit höchstens fünf Punkten Abstand.
Fließtext nach dem geometrisch abgegrenzten Tabellenbereich kann keine Kursmarke
entwerten. Zahlen müssen vollständig dem numerischen Feldformat entsprechen.
Fehlende Ziele werden niemals aus Prosa, Verhältnissen oder Nachbarwerten geschätzt.

**5/5 gemeldete Extraktionsfälle besitzen eindeutige, seitenbelegte Vorschläge.**
Das bedeutet keine Freigabe, Identitätsverifikation oder Änderung eines Datensatzes.
Alle bestehenden Werte und ursprünglichen Fehlerflags bleiben unverändert. Die
Qualitätszählung zeigt deshalb weiterhin fünf betroffene Dokumente. Reparaturen
stehen sowohl pro Empfehlung unter `layout_repairs` als auch dokumentweise in
`quality.documents[].repair_proposals`, mit Original-SHA, Ordinal, Zitaten,
Bounding-Boxen und `requires_manual_review=true`.

## Layoutbewusste Regeln

Der bisherige Assistent liest primär den Seitenvolltext. Dort verschachtelt die
Nachbarspalte zusammengehörige Sätze; zudem unterbrechen Trennstriche wie
„ver- kaufen“ und „Einstiegskur- ses“ die Worterkennung. Die neue Auswertung nutzt
ausschließlich bereits getrennte Regionen und ihre vertikal zusammengehörigen
Absätze. Sie entfernt Trennstriche nur für den Mustervergleich. Die Zitate
behalten Originalwörter und Trennstriche, normalisieren lediglich Leerraum und
enthalten Region, Bounding-Box, Seite, Dokument-SHA und Ordinal.

Vier getrennte Vorschlagstypen werden ausgewiesen:

- `partial_fraction`: Hälfte verkaufen beim ausdrücklich genannten ersten Kursziel.
- `after_target1`: Stopp auf Einstieg oder den ausdrücklich genannten ersten Zielkurs; ein unmittelbares „dann“ darf sich auf den
  vorausgehenden Teilverkaufssatz im selben Absatz derselben Spalte beziehen.
- `target2_sale`: zweite Hälfte bei Kursziel 2 verkaufen.
- `conditional_loss_exit`: ab genannter Haltedauer nur dann schließen, wenn die
  Position im Minus liegt. „20 Tagen oder länger“ bedeutet `days=20`,
  `threshold=at_least`, `condition=position_in_loss`. Die Zeiteinheit bleibt
  `unit=null`, sofern weder Kalender- noch Handelstage ausdrücklich belegt sind.

Der letzte Typ ist **kein `exit_after`**. Die bestehende Backtest-Engine kann ihn
noch nicht eigenständig validieren/simulieren und lehnt Spezifikationen mit
`conditional_loss_exit` oder `target2_sale` auch nach einer isoliert
nachgetragenen Reviewer-Freigabe ab. Eine Umsetzung von Tagesprüfung, Verlustbegriff,
Zeiteinheit und Ausführungspreis ist eine gesonderte Backtest-Erweiterung.
Stock-/Derivatnennungen werden separat als `instrument_scope` ausgegeben;
`instrument_unverified` bleibt ausdrücklich möglich. Widersprüche verhindern die
Übernahme in das gemeinsame Entwurfsfeld; einzelne Quellenkandidaten bleiben
sichtbar. Ein Entwurf bleibt auch bei übereinstimmenden Werten ungeprüft.

## Vorher–Nachher auf allen 118 Empfehlungen

| Strukturierter Vorschlag pro Empfehlung | Bisher V1.4 | Layout-Erweiterung |
| --- | ---: | ---: |
| Teilverkauf | 0 | 118 |
| Stoppanpassung im gemeinsamen Entwurf | 28 | 114 |
| Verkauf bei Ziel 2 | 0 | 117 |
| Bedingter Verlustausstieg | 0 | 104 |
| Unbedingter Zeitausstieg (`exit_after`) | 0 | 0 |
| Automatisch freigegebene Regeln | 0 | 0 |

Vier Empfehlungen nennen für unterschiedliche Instrumentkontexte sowohl Einstieg
als auch erstes Kursziel als neuen Stopp. Ihre getrennten Kandidaten bleiben
belegt sichtbar; das gemeinsame `after_target1`-Entwurfsfeld wird wegen des
Konflikts zurückgehalten. Deshalb sind 114 gemeinsame Stoppvorschläge vorhanden,
obwohl alle 118 Empfehlungen strukturierte Stoppkandidaten besitzen.

Alle 118 bleiben prüfpflichtig und `training_eligible=false`. Treffer können
mehrfach auf unterschiedlichen Seiten stehen; Tabellenwerte und Regelhinweise
sind keine Erfolgslabels. Die alten Kandidatenzähler bleiben kompatibel erhalten,
die neuen strukturierten Zähler stehen unter `structured_rule_recommendations`.
Die Nachanalyse enthält bewusst keine neu verifizierten historischen Identitäten.

[Maschinenlesbarer Auditbericht](hebeltrader-layout-rules-v14-audit.json) enthält
die fünf Quellenbindungen und Vorschläge. Acht Exportdateien wurden mit festem
Replay-Zeitpunkt zweimal auf Bytegleichheit geprüft. Vollständige 118er-Exporte
mit Originaltexten bleiben im privaten Artefaktordner.

## Reproduktion und Tests

```sh
export DATABASE_URL='sqlite:///file:/absolute/inventory.db?mode=ro&uri=true'
python -m scanner.hebeltrader prepare --run-at 2026-10-22T00:00:00+00:00 \
  --expected-count 118 --output-prefix /private/review/layout
ruff check .
ruff format --check .
python -m pytest -q
```

Vorhandene Ausgaben werden nicht überschrieben. Die Start-/Quellenkonfiguration
steht in [V1.4-Dokumentation](hebeltrader-preparation-v14.md).

Die Offline-Fixtures enthalten nur kurze Originaltabellen-/Regelausschnitte mit
Original-SHA-Referenzen; keine vollständigen PDFs. Die Testbytes bekommen einen
separaten synthetischen SHA, der ausdrücklich nicht als Original-PDF-SHA ausgegeben
wird. Getestet sind alle fünf Problemfälle sowie sechs über feste SHA-sortierte
Inventarpositionen ausgewählte weitere Empfehlungen. Hinzu kommen negative Tests
für Nachbarspalten, fehlende Aliase, doppelte Tabellen, Derivatüberschriften,
fehlende Ziele, Negation und SHA-Abweichungen. Echte Originalbytes und Vollbestand
wurden zusätzlich lokal lesend ausgewertet; die CI benötigt weder Hetzner noch PDFs.
