# Quellenpakete (Evidenz-Kanal)

Stand: 2026-10-30.

## Warum

Chart-/Sektor-Hypothesen allein reichen nicht (Pool-PIT: Blind 202/26 Residual
**B_chart_rank**; 27er Market Top-8 nur ~7/25). Identifikation braucht **datierte
Primärbelege** gegen Teaser-Hinweise — nicht Score-Retuning.

Ergebnis-Stufen: `docs/hebeltrader-path-to-ticker.md` — Offline-Paket mit ≥2
Kernhinweisen und ≥5 Peer-Emittenten setzt `identification=identified`
(`basis=historical_source_packet`). Batch: `python3 -m scanner.hebeltrader.detective.evidence_batch`.

## Harte Voraussetzungen

| Bedingung | Status 27er-Refs |
|---|---|
| Exaktes `publication_at` (Zeitzone) am Fall | **0/27** — Blocker |
| Paketdatei `{case_id}.json` unter `--source-packets` | noch keine echten Pakete |
| Belegte Inhaltsversion (`availability_evidence`) bei Archivabruf | Pflicht für historische Blind |

`publication_date` allein schaltet **keine** Pakete frei (`reference_scan`).

## Dateiformat

Pfad: `{source_packets_dir}/{case_id}.json` — JSON-**Array** von Dokumenten.

Pflichtfelder je Dokument:

- `company_name`, `ticker` (optional), `url`, `title`, `text`
- `source_kind`: `issuer` \| `regulator` \| `exchange` \| `archive` \| `secondary` \| `other`
- `published_at`, `retrieved_at` (ISO-8601 mit Offset)

Für nachträglich archivierte / spätere Abrufe zusätzlich eine **gebundene**
Verfügbarkeitsbasis (`raw_sha256` = `content_sha256`):

```json
{
  "source_available_at": "2026-10-25T12:00:00+00:00",
  "raw_sha256": "…",
  "availability_evidence": {
    "basis": "archived_snapshot",
    "source_url": "https://…",
    "observed_at": "2026-10-25T12:00:00+00:00",
    "content_sha256": "…"
  }
}
```

SEC-EDGAR-Filings (immutable Accession-URL): `basis: sec_edgar_filing_date`,
`source_url` unter `https://www.sec.gov/Archives/edgar/…`,
`source_available_at` = `published_at` (Filing-Datum). `observed_at` darf später
sein (Hash-Zeitpunkt). Ohne Binding bleibt late `retrieved_at` → `uncertain`
und historische Blind-Scans liefern `checked_candidates=[]`.

Validierung:

```bash
python3 -m scanner.hebeltrader.detective.source_packets docs/examples/source-packets/
```

Synthetisches Beispiel (kein Blindbeleg): `docs/examples/source-packets/SYNTHETIC-EXAMPLE.json`.

Erster Real-Pilot (SEC 10-Q, HT-001): `docs/examples/source-packets/pilot/` — nach
SEC-Binding: 6 checked Identitäten, aber weiterhin
`insufficient_specific_primary_evidence` (Teaser ohne Eigenamen).

Named-Clue-Pilot (HT-027 / Clario+Solventum): `docs/examples/source-packets/pilot-named/` —
zwei bestätigte Kernhinweise (`Clario`, `Solventum`, Score 105) →
`plausible_hypothesis`. Offline bleibt `not_identified` (Falsifikations-/Gegenkandidaten-Gate).

Original-Anker-Lücke: `docs/examples/source-packets/pilot-original-anchors/` —
**0/27** Refs mit ≥2 nativen spezifischen Ankern. HT-023 (AbbVie im Headline)
über `issuer_literal` → ABBV Top-1 / `plausible_hypothesis` (1/2 Hinweise).

## Operator-Checkliste (nächster echter Fall)

1. Beim Report-Kauf / Teaser-Abruf **`publication_at`** notieren (nicht nur Datum).
2. Vor Cutoff verfügbare IR/SEC/Ad-hoc-Quellen sichern (Text + URL + Hash).
3. Mindestens **5 Gegenkandidaten**-Dokumente gleicher Spezifität ablegen.
4. Offline-Scan: `reference_scan --inputs … --source-packets … --snapshots …`
5. Ranking einfrieren **bevor** Lösungen gelesen werden.

## Abgrenzung

- Market-Top-8 = unverifizierte Chart-Vorschläge (Tie-Break), keine Identifikation.
- Keine erfundenen Teasertexte oder rückdatierten „war öffentlich“-Behauptungen.
- Blind 202/26 Freeze bleibt unangetastet (kein Score-Retuning).
- **Publisher-Call-PDFs sind keine Quellenpakete** (Resolutionsleak). Siehe
  `docs/hebeltrader-pdf-resolution-index.md`. Scan-Inputs dürfen nur die
  `publication_at`-Guess daraus übernehmen.
