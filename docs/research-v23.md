# Scanner V6 V2.3 – Reale Teaser-Kandidatenidentifikation

## Urteil

Der Datenfluss funktioniert mit echten archivierten SEC-Daten, aber die Anwendung ist noch nicht
allgemein für unbekannte Börsenteaser verwendbar. Der reale Blindversuch blieb korrekt
`unresolved`: In der teaserunabhängig ausgewählten 50-Unternehmen-Stichprobe belegten mehrere
Unternehmen USA plus Gewinnanstieg, während der entscheidende Hinweis „Versicherer“ nicht belegt
war. Das Ergebnis ist in [research-v23-e2e.json](research-v23-e2e.json) maschinenlesbar.

V2.3 behauptet weder globale Abdeckung noch eine Trefferwahrscheinlichkeit. Der Detektiv liefert
höchstens plausible Top-3-Kandidaten mit Evidenz, Widersprüchen und offenen Annahmen. Er erzeugt
keine Kaufentscheidung.

## Betriebsarten

| Modus | Daten | Netzwerk | Kennzeichnung |
|---|---|---|---|
| `fixture` | bestehende synthetische Testdaten | nie | `fixture_limited`, `real_market_data=false` |
| `cached_research` | normalisiertes Snapshot plus geprüfte SHA-256-Rohquellen | nie | tatsächliche Coverage und Datenalter |
| `live_research` | begrenzter SEC-Abruf, danach identisches Snapshot | nur explizit während Analyse | Request-Limit, Teilfehler, Kosten und Auswahlverfahren |

Der API-Start baut lediglich eine lazy Quelle. Er ruft keine externe URL auf. Live-Modus benötigt
gleichzeitig `DETECTIVE_LIVE_ALLOW_NETWORK=true`, einen positiven Request-Grenzwert und einen
`SEC_USER_AGENT` mit Kontaktadresse. Der HTTP-Endpunkt verlangt im Live-Modus zusätzlich
`X-Research-Authorization`, das konstantzeitlich gegen `DETECTIVE_LIVE_API_TOKEN` geprüft wird.
Fehlt dieses Server-Secret, antwortet der Endpunkt mit 503; falsche oder fehlende Request-Tokens
werden vor jeder Recherche mit 403 abgewiesen. Die CLI ist ein lokaler Administrationspfad und
verwendet diesen HTTP-Schutz nicht.

Für `N` Kandidaten sind exakt `1 + 2N` Requests reserviert:
Universum, Submissions und Company-Facts. Kandidaten werden vor dem Teaser durch
`sha256("sec-cik:" + CIK)` ausgewählt; mehrere Listings derselben CIK zählen als ein Emittent.
Ein unzureichendes Gesamtlimit beendet den Lauf vor dem ersten Abruf. Pro HTTP-Request gelten
standardmäßig 10 Sekunden und für den Gesamtlauf 120 Sekunden; beide Grenzen sind konfigurierbar
und hart auf 30 beziehungsweise 300 Sekunden begrenzt. Ein Lock verhindert mehrfachen parallelen
Erstaufbau im selben Prozess. Antworten liefern pro Kandidat höchstens acht Evidenzobjekte und
weisen Gesamt-, Rückgabe- und Auslassungszahl aus. Das vollständige SHA-geprüfte Archiv bleibt
lokal abrufbar.

CLI und API rufen dieselbe `build_detective`-Factory auf. Beide liefern `research_mode`,
`candidate_source.coverage`, `identification`, Top-3-Kandidaten und dieselben Evidenzstrukturen.

## Fakten und Point in time

Ein 10-Q oder 8-K wird als `regulatory_filing` gespeichert. Das Formular allein belegt weder
positive Quartalszahlen noch Gewinnüberraschung oder Prognoseanhebung. Der begrenzte deterministische
XBRL-Extraktor verarbeitet derzeit Umsatz und Nettoergebnis. Eine gerichtete
`year_over_year_increase`/`decrease` entsteht nur bei gleichem Fiskalabschnitt, Vorjahr und
kalendergleichem Zeitraum. Sonst bleibt der Fakt `reported_value` mit Status `unknown`.

Jeder Fakt enthält Kennzahl, Wert, Einheit, Periode, gegebenenfalls Vergleichswert und -periode,
SEC-URL, JSON-Fundstelle, Veröffentlichungs-/Verfügbarkeits-/Abrufzeit, Methode, Status und
Rohdaten-SHA. Wenn die Submission zur Accession vorhanden ist, gilt deren SEC-Acceptance-Zeit.
Liegt nur das XBRL-`filed`-Datum vor, wird konservativ das Tagesende verwendet. Spätere Evidenz
wird aus historischen Analysen ausgeschlossen. Ein heute geladener SEC- oder GLEIF-Identitätssatz
ist ohne datierten Beleg keine historische Stammdatenbestätigung.

## Quellen und internationale Abdeckung

- **SEC EDGAR:** kostenloses US-Filer-Universum, Submissions und Company-Facts. Offizielle
  Zugriffsregeln: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- **GLEIF:** tatsächlich implementierter zweiter Adapter für globale LEI-Rechtsträgerdaten. Die
  API ist kostenlos und ohne Anmeldung; Daten stehen laut GLEIF unter CC0:
  https://www.gleif.org/en/meta/lei-data-terms-of-use und
  https://www.gleif.org/en/lei-data/gleif-api. GLEIF liefert Identität, keine Nachrichten.
- **Deutschland:** Das Unternehmensregister bietet kostenlose Einzelsuche, aber die dokumentierte
  Oberfläche verwendet Suche/Captcha und belegt keinen kostenlosen Massen-API-Zugang für diesen
  Anwendungsfall: https://www.unternehmensregister.de/en/howto/search und
  https://www.unternehmensregister.de/en/howto/costs.
- **Österreich/Schweiz/Europa:** Offizielle Börsen- und Emittentenportale stellen Meldungen bereit;
  ein dokumentierter kostenloser API-Zugang mit historischer Massenabfrage und passenden
  Nutzungsrechten wurde nicht belegt. SIX bewirbt Marktdaten-APIs als Datenprodukt. Deshalb wurde
  keine Web-Scraping-Schnittstelle als fertiger Provider ausgegeben.

Damit fehlen weiterhin belastbare allgemeine Unternehmensnachrichten, vollständige Branchenfelder,
historische WKN/ISIN-/Listing-Gültigkeit und breite DE/AT/CH/EU-Abdeckung. Budgetverbrauch im PR:
`0 EUR`.

## Reale End-to-End-Abnahme

Der am 24.10.2026 vorab festgelegte Blindteaser enthielt weder Firma noch Ticker, WKN oder ISIN:

> Ein US-Versicherer meldet einen Gewinnanstieg. Eine konkrete Gesellschaft oder Kennung wird
> nicht genannt.

Der echte Lauf verwendete 50 per CIK-Hash ausgewählte Emittenten aus 10.425 SEC-Listings bzw.
8.022 eindeutigen CIKs. Ergebnis: 50 Identitäten, 22.975 Filing-Ereignisse, 8.988 extrahierte
Fakten, fünf sichtbar protokollierte Company-Facts-Lücken und `unresolved/ambiguous_candidates`.
Die drei Top-Kandidaten belegten lediglich USA und Nettoergebnisanstieg; „Versicherer“ blieb bei
allen ungeprüft. Das ist ein nachvollziehbarer realer Identifikationsversuch, kein Erfolgsnachweis.
Die untersuchte Stichprobe entspricht 0,6233 % des SEC-Emittentenuniversums. Branchen waren nur
für 11 von 50 (22 %) und unterstützte Unternehmenskennzahlen für 34 von 50 (68 %) verfügbar.
Recall@10/50 ist für diesen Stichprobenlauf nicht messbar. Nicht abgedeckt sind Nicht-SEC-US-Titel
sowie Deutschland, Österreich, Schweiz und das übrige Europa.

Abnahmematrix:

| Fall | Datenbasis | Ergebnis |
|---|---|---|
| A Blindteaser | echte SEC-Rohdaten, feste Hash-Auswahl | ausgeführt, korrekt `unresolved` |
| B spätere Evidenz | synthetische Zeitgrenzfälle plus echte SEC-Acceptance-Semantik | ausgeschlossen |
| C unvollständige Daten | Offline-Regression und echter Lauf | `unresolved` |
| D Widersprüche | deterministischer Mehrkandidaten-Snapshot | Land/Branche/Kennzahl senken Ranking |
| E Quellenausfall | HTTP-/Cache-Regression | expliziter `unavailable`/`partial`-Status |
| F kein Lösungswissen | echter SEC-Lauf | Auswahl nur aus CIK-Hash, vor Recherche |

## Termius-/Docker-Abnahme ohne Deployment

Der Offline-Test liest ein vorhandenes Archiv, startet keine Compose-Dienste und greift nicht auf
PostgreSQL zu:

```bash
cd /opt/aktien-chancen-scanner-v5
git fetch origin feat/real-teaser-identification-v2-3
git switch --detach origin/feat/real-teaser-identification-v2-3
docker build -t scanner-v23-check .
mkdir -p reports/research-v23
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD/reports/research-v23:/reports/research-v23" \
  scanner-v23-check python -m scanner.hebeltrader.detective.cli \
  --text-file /reports/research-v23/blind-teaser.txt \
  --publication-at 2026-10-24T00:00:00Z \
  --research-mode cached_research \
  --research-snapshot /reports/research-v23/snapshot.json \
  --output /reports/research-v23/result-offline.json
```

Ein erstmaliger realer SEC-Aufbau benötigt bewusst Netzwerk und explizite Limits:

```bash
docker run --rm --read-only --tmpfs /tmp \
  -e SEC_USER_AGENT='ScannerV6 kontakt@example.org' \
  -v "$PWD/reports/research-v23:/reports/research-v23" \
  scanner-v23-check python -m scanner.hebeltrader.detective.cli \
  --text-file /reports/research-v23/blind-teaser.txt \
  --publication-at 2026-10-24T00:00:00Z \
  --research-mode live_research --allow-network \
  --max-candidates 50 --max-requests 101 \
  --research-cache-dir /reports/research-v23/sec-cache \
  --research-snapshot /reports/research-v23/snapshot.json \
  --output /reports/research-v23/result.json
```

Diese Befehle führen keine Migration aus, starten keinen Scanner-Worker und berühren weder Immich
noch vorhandene Container oder Datenbanken.
