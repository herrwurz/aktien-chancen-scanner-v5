# Öffentliche HEBELTRADER-Ausgaben automatisch erfassen

Ergänzung zu V3.1 / PR #29. Der vorhandene interne Kandidatenkatalog bleibt unverändert;
`publisher_catalog.py` verarbeitet ausschließlich öffentliche Herausgeberseiten.

## Implementiert

`watch` liest standardmäßig `https://www.boersenmedien.de/hebeltrader` und entdeckt die
neuesten öffentlichen Produktseiten. Nur HTTPS-Links im HEBELTRADER-Produktpfad werden
verfolgt. Die Zahl ist begrenzt (Standard drei, maximal zehn). Das gemeinsame HTTP-Budget,
Robots-Prüfung und Rohdatenarchiv bleiben erhalten. Keine Login-/Bestell-/PDF-Downloads.

Der Parser liest gezielt Ausgabe, Autor, Überschrift, Erscheinungsdatum und öffentlichen
Teasertext. Kaufbereich, andere Ausgaben, Navigation, Script-/Formularinhalte und versteckte
Markup-Texte werden nicht als Teaser übernommen. Unbekanntes oder widersprüchliches Layout
führt zu einem protokollierten Fehler; es gibt keinen Ganzseiten-Fallback. Die bisherige
RSS-/Suchfunktion bleibt parallel erhalten.

Kalenderdaten wie `2026-10-28` werden als `publication_date` gespeichert. Ohne Zeitzone und
Uhrzeit bleibt `publication_at` leer. Es wird keine Mitternacht oder historische
Verfügbarkeit erfunden. Die vorhandene Engine legt anschließend den Fall, das eingefrorene
Ranking und die lokale Registererweiterung an; fehlende Unternehmensbelege dürfen zur
Enthaltung führen.

## Reproduzierbarer Einzellauf

```bash
python -m scanner.hebeltrader.detective.investigate_cli watch \
  --allow-network --once --catalog-limit 3 --max-requests 16 \
  --root data/catalog-pilot --register-path data/catalog-pilot/case-register.md
```

Denselben Befehl mit demselben ROOT wiederholen, um Deduplizierung zu prüfen.
`--no-catalog` erhält den bisherigen reinen RSS-/Suchpfad. Ohne `--once` gilt die vorhandene
Intervallschleife; sie wird durch diese Änderung nicht gestartet. Im read-only Docker-
Container ROOT und Registerpfad in ein eigenes beschreibbares Datenvolume legen.

„Neu“ bedeutet **erstmals von diesem Monitor erfasst**, nicht neu veröffentlicht.
Beim ersten Lauf können deshalb schon ältere, öffentlich zugängliche Ausgaben erfasst
werden. Benachrichtigungen bleiben im lokalen Postausgang; keine externe Zustellung.
Nach 24 Stunden ist eine Neubewertung möglich, ohne unveränderte Fälle erneut zu melden.

## Tatsächlicher Prüflauf am 28.10.2026

- Erster Lauf: **198/26, 199/26 und 200/26** automatisch entdeckt, öffentliche Texte
  extrahiert, drei Fälle angelegt und drei lokale Erstmeldungen gespeichert.
- Autor und Kalenderdatum stimmen mit den Produktseiten überein. Keine Uhrzeit vorgegeben.
- Alle drei Aktienentscheidungen blieben **nicht ausreichend identifizierbar**. Null
  qualifizierte Aktienidentifikationen; das ist kein automatisches Reproduzieren des
  assistentengestützten SLB-Treffers.
- Zweiter Lauf: **null neue Fälle, null neue Analysen, drei Dubletten**, keine neue Meldung.
- Beide Läufe ohne technischen Fehler; Bing als blockierte Suchquelle ausgewiesen.
- Lokale vollständige Suite: **751 bestanden, acht PostgreSQL-Tests übersprungen**;
  eine bestehende Starlette-/AnyIO-DeprecationWarning. Ruff und Docker-Build erfolgreich.
- Review des Katalogpfads: keine reproduzierten wesentlichen Befunde. Regressionen prüfen
  fremde/PDF-Links, Quellen-/Ausgabenkonsistenz, sichtbaren Teaserbereich, Datumspräzision
  und wiederholte Erfassung.

Zeitstempel, Quellenabrufe, Fall-IDs, Journalintegrität und Ergebnisse stehen im
[maschinenlesbaren Nachweis](hebeltrader-catalog-acceptance.json). Rohseiten und vollständige
Teaser liegen im lokalen Datenarchiv, nicht als vollständige Artikel im Repository.
Die bereits bekannten Fälle 198/200 werden nicht als neue Blindtests oder Treffer gezählt.

## Nächste verbleibende Lücke

Die automatische **Erfassung** ist mit echten Seiten nachgewiesen. Für zuverlässige
Aktienidentifikation fehlen weiterhin globale zulässige Suchabdeckung, systematisch
zugeordnete Primärquellen und mindestens fünf belegte Gegenkandidaten pro passendem Fall.
Keine Trefferquote aus diesem Erfassungstest ableiten. Kein Hetzner-Lauf, kein Merge,
kein produktives Deployment, keine Änderungen an Immich oder fremden Datenbanken.
