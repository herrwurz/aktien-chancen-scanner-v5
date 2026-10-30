# Quellenpakete (Evidenz-Kanal)

Stand: 2026-10-30.

## Warum

Chart-/Sektor-Hypothesen allein reichen nicht (Pool-PIT: Blind 202/26 Residual
**B_chart_rank**; 27er Market Top-8 nur ~7/25). Identifikation braucht **datierte
Primärbelege** gegen Teaser-Hinweise — nicht Score-Retuning.

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

Für nachträglich archivierte Inhalte zusätzlich:

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

Validierung:

```bash
python3 -m scanner.hebeltrader.detective.source_packets docs/examples/source-packets/
```

Synthetisches Beispiel (kein Blindbeleg): `docs/examples/source-packets/SYNTHETIC-EXAMPLE.json`.

Erster Real-Pilot (SEC 10-Q, HT-001): `docs/examples/source-packets/pilot/` — Evidenz weiterhin
`insufficient_specific_primary_evidence`, weil der Teaser keine Eigenamen trägt.

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
