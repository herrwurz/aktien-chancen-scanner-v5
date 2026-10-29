# V3.1 – Teaser Intelligence Scanner

V3.1 baut auf PR #28 (`212cc20`) auf. PR #28 bleibt Voraussetzung und wird nicht gemergt.
Die [Gap-Analyse und Umsetzung](superpowers/plans/2026-10-28-teaser-intelligence-v31.md)
trennt vorhandene Funktionen von den Ergänzungen. SEC-/Tiingo-, Markt-, Volumen- und
V3-Recherchemodule bleiben erhalten; V3.1 erfindet keine globale Datenversorgung.

## Neue Funktionen

- Autor, Ausgabe, Originalquellen-URL und tatsächlicher Quellenabruf zusätzlich zu
  Text/URL/PDF/Screenshot. Fall-ID `TI-…`; SHA256 der kanonischen Originaleingabe und
  getrennter Hash des extrahierten Teasers.
- Quellen-/Inhaltsabgleich einschließlich alternativer URLs und späterer Textkorrekturen.
  Neue Ausgabe unter gleicher URL ist ein neuer Fall, wenn sich der Inhalt unterscheidet.
- Eigene append-only Hashkette `ROOT/cases/cases.jsonl` mit Dateisperre und fsync.
  Zustände: `neu`, `in_analyse`, `hypothese`, `ungeloest`, `bestaetigt`, `widerlegt`.
  Erste Prognose und spätere Analysen bleiben getrennt; Auflösung/Korrektur hängt neue
  Einträge an. Ein Hashfehler führt zum Abbruch, nicht zum stillen Reparieren.
- Post-freeze Auflösung mit Aktie/Identität, optionaler Call-WKN, Herkunft, Fehleranalyse
  und Algorithmusänderung. Nutzerbestätigung bleibt von Produktverifikation getrennt.
- Kompakter `report.md` zusätzlich zu eingefrorenem JSON, Matrix und Quellenarchiv.
- Öffentlicher RSS-/Atom-Entdeckungskanal. Der echte Feed
  `https://www.deraktionaer.de/aktionaer-news.rss` wurde am 28.10.2026 mit zehn Einträgen
  erreicht. Keine Login-/Paywall-Umgehung. RSS-Titel sind keine Unternehmensbeweise.
- Qualitätsauswertung aus unveränderten Erstprognosen: Top1/Top3, expliziter Nenner,
  ungelöste Fälle, falsche als identifiziert erklärte Aktien, Recherchezeit, heruntergeladene
  Primär-/Gesamtdokumente und Fallverlauf. Quellenzählung ist keine weltweite Coverage.

Die vorhandene breite Suche, fünf belegten Gegenkandidaten, Matrix und Falsifikation
werden wiederverwendet. Ergebnisse unterscheiden `likely_identified`,
`plausible_hypothesis` und `insufficient_evidence`. Der Evidenzscore ist keine
Wahrscheinlichkeit. Die Kernregeln aus der zentralen Fallhistorie bleiben verbindlich.

## Zeitvertrag und Blindtests

`event_at`, `published_at`, `source_available_at`, `retrieved_at` und
`content_revision_at` bleiben getrennt. Fehlende Ereigniszeit wird nicht erfunden.
Publikation allein beweist nicht die damalige Verfügbarkeit des heute abgerufenen Inhalts.
Beobachtete Originale vor dem Cutoff sind verwendbar; spätere Abrufe ohne belegte
Archivversion bleiben unsicher. Spätere Revisionen bestätigen keine früheren Hinweise.

Für ein später abgerufenes, historisches Quellenpaket muss der Betreiber die damalige
**gleiche Inhaltsversion** ausdrücklich belegen:

```json
{
  "source_available_at": "2026-10-25T12:00:00+00:00",
  "raw_sha256": "SHA256_DER_TATSAECHLICHEN_ARCHIVVERSION",
  "availability_evidence": {
    "basis": "archived_snapshot",
    "source_url": "https://autorisierte-archivquelle.example/original",
    "observed_at": "2026-10-25T12:00:00+00:00",
    "content_sha256": "SHA256_DER_TATSAECHLICHEN_ARCHIVVERSION"
  }
}
```

Das ist ein Importvertrag mit Betreiberprovenienz, keine automatische externe Signaturprüfung.
Eine freie Behauptung wie „war damals öffentlich“ genügt nicht. Ungültige oder zeitzonenlose
Zeitwerte bleiben unbekannt. Historische Blindanalyse verwendet kein Live-Web.

Der Rankingprozess liest keine Register oder Lösungen. In `--historical-blind` öffnet
auch der Workflow das Falljournal erst **nach** Einfrieren des Rankings. Für strenge
Prozessisolation das bestehende netzwerklose Docker-Verfahren verwenden und nur Eingaben,
Quellenpaket und Ausgabeverzeichnis mounten, niemals Lösungsdateien. Registerexport und
Auswertung erfolgen anschließend im Betreiberprozess. Dateischreibschutz/Hashketten sind
kein gegen Administratoren geschütztes oder extern signiertes WORM-Archiv.

Die 18 bekannten Fälle bleiben Entwicklungsfälle. ADI/LSCC, CRM/Zoom und JPM/GS werden
mit getrennten Eingabe-/Lösungsdateien auf fehlende Originale geprüft. Die vorhandenen
kurzen ADI-/CRM-Titel erzwingen ohne Quellen **keine** Lösung. JPMs Original fehlt.
Es gibt keine erfundenen vollständigen Originalteaser oder früheren Top-3-Listen.

## Bedienung ohne neue Zugangsdaten

```bash
python -m scanner.hebeltrader.detective.investigate_cli analyze \
  --text-file /pfad/teaser.txt --headline 'Originalüberschrift' \
  --publisher 'DER AKTIONÄR' --author 'Rudolf Wittmer' --issue '201/26' \
  --publication-at '2026-10-28T10:00:00+01:00' \
  --allow-network --max-requests 40 \
  --primary-domains /pfad/gepruefte-ir-hosts.json \
  --root data/teaser-v31 \
  --register-path docs/hebeltrader-identification-rules.md
```

`--url` ruft die öffentliche Originalseite ab. Für einen rechtmäßig bereitgestellten
RSS-/Textauszug dienen `--original-source-url` und `--source-retrieved-at` nur der
Provenienz; sie lösen keinen angeblichen Originalseitenabruf aus. Keine Auflösung in
Teasertext/Quellenpaket geben. Eine spätere Auflösung ausschließlich separat erfassen:

```bash
python -m scanner.hebeltrader.detective.investigate_cli resolve \
  --root data/teaser-v31 --case-id TI-FALLID \
  --resolution-file /getrennt/aufloesung.json \
  --register-path docs/hebeltrader-identification-rules.md
python -m scanner.hebeltrader.detective.investigate_cli quality --root data/teaser-v31
```

Auflösungsdatei:

```json
{
  "asset_id": "KANDIDATEN_ID_ODER_VERIFIZIERTE_IDENTITAET",
  "name": "Tatsaechlich aufgeloestes Unternehmen",
  "basis": "user",
  "source": "Beleg oder eindeutige Herkunft der Nutzeraufloesung",
  "error_analysis": "Warum war die Erstprognose richtig oder falsch?",
  "algorithm_change": "Welche allgemeine Regel muss korrigiert werden?"
}
```

Optional `call_wkn` (sechs Zeichen). Der Herkunftsstatus lautet
`original_reported_by_user` bzw. `original_reported_by_source`; `product_verification`
bleibt `not_verified`. Das ist weder ein bestätigter Originalschein noch ein nachgewiesen
handelbarer alternativer Call. Produktrecherche bleibt nachgelagert und manuell zu prüfen.

Für echte neue Blindfälle **vor** der Recherche `--evaluation-class prospective_blind
--new-blind-case` verwenden. Raten benötigen zusätzlich eine erst nach dem Freeze belegte
Auflösung (`confirmed_at`, `original_sha256` des eingefrorenen Teasers). Bekannte Fälle
bleiben `development_regression`, spätere Recherche zu alten Teasern `retrospective`.
Unaufgelöste vorregistrierte Fälle bleiben im Nenner der ungelösten Kohorte. Prozentwerte
werden ausschließlich für belegte aufgelöste unabhängige Fälle mit ausgewiesenem Nenner
berechnet; Betreibererklärungen beweisen allein keine methodische Unabhängigkeit.

## Monitoring, API und Zentralregister

```bash
python -m scanner.hebeltrader.detective.investigate_cli watch \
  --allow-network --once --max-requests 40 --root data/teaser-v31 \
  --register-path docs/hebeltrader-identification-rules.md
```

Ohne `--once` bleibt der bestehende Intervallbetrieb erhalten. Zusätzliche öffentliche
Feeds mit `--discovery-feed URL` (mehrfach, maximal acht). Der Herausgeberfeed enthält
nur die letzten Einträge; lange Pollintervalle können Veröffentlichungen verpassen.
Die Verfügbarkeit eines Feeds garantiert weder vollständige HEBELTRADER-Abdeckung noch
fünf plausible Gegenkandidaten. Bing-Ausfälle und blockierte Quellen stehen im Bericht.

Die vorhandene Webansicht ergänzt Autor/Ausgabe, Fall-ID und getrennte Auflösung.
Neue geschützte API-Endpunkte: `GET /api/hebeltrader/cases`,
`GET /api/hebeltrader/cases/{id}`, `POST /api/hebeltrader/cases/{id}/resolution`,
`GET /api/hebeltrader/quality`. Zugriff verlangt `DETECTIVE_LIVE_API_TOKEN` im Header
`X-Research-Authorization`; Token fehlt → 503, falsch → 403. Kein Token im Journal.

Jeder Lauf ergänzt zunächst `ROOT/case-register.md`. Die CLI synchronisiert danach die
zentrale MD-Datei append-only; jeder Exportblock enthält den Ereignishash und wird nur
einmal angehängt. Die API schreibt die zentrale MD-Datei nur mit dem explizit gesetzten
`DETECTIVE_CASE_REGISTER`-Pfad; sonst bleibt die lokale Erweiterung erhalten. Nachholen:

```bash
python -m scanner.hebeltrader.detective.investigate_cli register \
  --root data/teaser-v31 --register-path docs/hebeltrader-identification-rules.md
```

Docker benötigt ein eigenes persistentes, beschreibbares ROOT-Verzeichnis. Bei einem
read-only Container `--register-path /data/case-register.md` angeben und das Zentralregister
anschließend im Betreiberprozess synchronisieren. Keine produktive Migration erforderlich.
Kein Dienst wurde gestartet, kein Hetzner-Zugriff behauptet, keine Orders oder Abos.

Der [Abnahmebericht](teaser-v31-acceptance.md) enthält den tatsächlichen Quellenlauf,
Regressionsergebnisse, offenen Datenbedarf und die weiterhin offene fachliche Abnahme.
