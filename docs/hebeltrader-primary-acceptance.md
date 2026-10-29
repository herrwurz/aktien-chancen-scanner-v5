# Abnahmebericht: primärer HEBELTRADER-Detektiv

Prüfdatum: 28.10.2026. **Fachliche Abnahme offen; noch keine Produktionsfreigabe.**
Neuer Branch `feat/hebeltrader-primary-detector`, Ausgangsbasis main `e504ad9`.
PR #27 und dessen SEC-/Tiingo-Nachweise sind ein separates Vorhaben.

Implementiert und technisch geprüft sind die neue Startseite, Text/URL/Screenshot/PDF,
archivierte Quellen, dynamische Kandidatengenerierung ohne festes Aktienuniversum,
einheitliche Vergleichsmatrix, Gegenkandidaten-Gate, aktive Falsifikation, Top 3,
Enthaltung, getrennte Produktrecherche, eingefrorene Rangliste und spätere Auswertung.
Der öffentliche Poller dedupliziert und schreibt lokale Benachrichtigungen; kein Dienst
wurde gestartet. Die vorhandenen Extraktions- und Verifikationskomponenten werden wiederverwendet.

## Tatsächlicher Nachweis

- Alle **18 historischen Einträge** maschinenlesbar erfasst: 17 berichtete Auflösungen,
  Williams ungelöst. Null vollständige Originalteaser, null exakte Teaserzeitpunkte und
  null vollständige ursprüngliche Top-3-Ranglisten im Register. Diese Fälle wurden
  **nicht** als neue Blindtests ausgegeben. Die bestehenden Lösungen liegen nicht im
  Suchkontext des neuen Analysepfads.
- Neue Regressionen prüfen unter anderem Transaktionsart, Unternehmensbezug von Zahlen,
  Quartalsvergleich, harte Gegenbelege, fünf tatsächlich belegte Alternativen,
  nachträgliche Quellen, Falsifikation, Ranglistenintegrität, Produktsuch-Gates,
  Quellensicherheit, Deduplizierung und Benachrichtigungen. Sie verwenden synthetische
  Unternehmen und belegen keine historische Trefferquote.
- Vollständige lokale Suite, Ruff und Docker-Prüfung: siehe versionierter
  [JSON-Nachweis](hebeltrader-primary-acceptance.json). Übersprungene PostgreSQL-Tests
  benötigen die isolierte Testdatenbank; die GitHub-CI richtet diese selbst ein.
- Ein isolierter Docker-Einzellauf mit `--network none --read-only` erzeugte aus einem
  absichtlich informationsarmen Text korrekt `not_identified`. Die eingefrorene
  Rangliste wurde erneut eingelesen und ihr SHA256 erfolgreich geprüft.
- Eine echte öffentlich zugängliche DER-AKTIONÄR-Seite wurde abgerufen und mit Rohdatenhash
  archiviert. Das ist ein allgemeiner HEBELTRADER-Marketingartikel, **kein Nachweis einer
  unbekannten Aktie**. Suchzugriff und Zeitstempelgrenzen stehen im JSON-Nachweis.

Es gibt **null unabhängig blind geprüfte reale Teaser**, null als richtig verifizierte
neue Aktienidentifikationen und keinen verifizierten beworbenen Original-Call. Es wird
keine Erfolgsquote behauptet.

## Offene Voraussetzungen

1. Ein neuer vollständiger öffentlicher Teaser oder ein vom Betreiber autorisiert
   bereitgestelltes Original, dessen Lösung beim Einfrieren noch unbekannt ist.
2. Erreichbare, zulässige öffentliche Suche und datierte Original-Unternehmensbelege
   für mindestens sechs plausible Unternehmen. Die getestete Bing-RSS-Suche wird durch
   Robots-Regeln blockiert. Es findet keine Umgehung statt. Fehlende Suchresultate
   erlauben keine Aussage über nicht existierende Kandidaten.
3. Geprüfte Zuordnung offizieller Investor-Relations-Hosts zu Unternehmen; explizite
   Metadaten sind derzeit Voraussetzung automatischer Unternehmenszuordnung. Das begrenzt
   den Recall. Volltextverständnis, Mehrsprachigkeit und Quellenabdeckung sind begrenzt.
4. Spätere belegte Auflösung getrennt von Eingabe/Recherche archivieren; dann unveränderte
   Top 3, Fehlzuordnungen und Enthaltungen bewerten. Bekannte 18 Fälle bleiben Entwicklung.
5. Optional offizielle Emittentenhost-Konfiguration und vollständige Produktbelege.
   Eine tatsächliche HEBELTRADER-Call-Bestätigung wird noch nicht automatisiert freigegeben.

Keine neuen Zugangsdaten oder kostenpflichtigen Tarife sind für den Offlinepfad nötig.
Für die optionale Netzwerk-API muss der Betreiber ein lokales Recherchetoken setzen;
Login-/Paywall-Zugänge wurden weder benutzt noch angefordert. Für automatischen Betrieb
muss der Betreiber den dokumentierten Poller bewusst starten und ein persistentes,
beschreibbares eigenes Datenverzeichnis bereitstellen. Externe Nachrichtenzustellung
ist nicht eingerichtet. Kein Hetzner-Lauf wurde durch Codex durchgeführt oder behauptet.

**Merge-Empfehlung:** vorerst als Draft prüfen; keine fachliche Produktionsfreigabe,
bis mindestens ein realer unbekannter Teaser mit vollständig archiviertem Vergleich und
später belegter Auflösung durchgelaufen ist. Keine automatischen Merges, Deployments,
Datenbankmigrationen im Produktivsystem oder Wertpapierorders.
