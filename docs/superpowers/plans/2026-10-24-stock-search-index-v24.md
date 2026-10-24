# V2.4 Implementierungsplan – Aktien-Suchindex und Candidate Retrieval

Eigenständiger Folge-PR: **Scanner V6 V2.4 – Intelligenter Aktien-Suchindex und Candidate Retrieval**.
Ausgangsbasis ist `main` nach einem separaten Merge von PR #19; PR #19 selbst enthält nur Design
und P0-Korrekturen.

1. **Verträge und Abnahmekorpus einfrieren.**
   - Dateien: `scanner/research_index/protocols.py`, `scanner/research_index/models.py`,
     `tests/fixtures/research_v24/evaluation-manifest.json`, `tests/test_research_v24_contracts.py`.
   - Die sechs `research.*`-Schnittstellen, PIT-Felder, Pagination und Coverage definieren.
   - Echte Fälle, synthetische Fälle und erwartetes `unresolved` vor Implementierung registrieren.

2. **SQLite-FTS5-Schema und reproduzierbaren Builder implementieren.**
   - Dateien: `scanner/research_index/schema.sql`, `builder.py`, `manifest.py`,
     `tests/test_research_index_builder.py`.
   - V2.3-Snapshots und SEC-Roharchive offline importieren, Zeilen deterministisch sortieren,
     Fremdschlüssel prüfen, Datenbank optimieren, SHA-256-Manifest schreiben.
   - Build in temporärer Datei; erst nach Integritätsprüfung atomar veröffentlichen.

3. **Point-in-time-Repository bauen.**
   - Dateien: `scanner/research_index/repository.py`, `pit.py`,
     `tests/test_research_index_point_in_time.py`.
   - Acceptance, spätere Korrekturen, Nachmeldungen, Identitätswechsel und fehlende Zeitstempel
     regressieren. Ohne `as_of` keine historische Suche.

4. **Stage-A-Candidate-Retrieval implementieren.**
   - Dateien: `scanner/research_index/retrieval.py`, `query.py`,
     `tests/test_candidate_retrieval.py`.
   - Strukturfilter, FTS5/BM25, kanalweise Reserve und deterministische Fusion auf maximal 50.
   - `insufficiently_constrained` und Out-of-index-Fälle explizit ausgeben.

5. **Stage-B-Evidenzprüfung anbinden.**
   - Dateien: `scanner/hebeltrader/detective/index_source.py`,
     `scanner/hebeltrader/detective/service.py`, `tests/test_detective_v24_e2e.py`.
   - Bestehenden Clue- und Rankingcode wiederverwenden; alle 50 zeitgültig prüfen, danach Top-3.
   - Bestätigt, widerlegt und unbekannt getrennt halten; Evidenzantworten begrenzen.

6. **Gemeinsame Read-only-API/CLI bereitstellen.**
   - Dateien: `scanner/research_service.py`, `scanner/main.py`,
     `scanner/research_index/cli.py`, `tests/test_research_v24_api.py`.
   - `research.universe/candidates/events/fundamentals/prices/coverage` mit Cursorlimits anbieten.
   - Kein Netzwerk beim Start; Live-Aktualisierung nur als separater, autorisierter Build-Befehl.

7. **Chancen-Scanner-Adapter ohne Kaufentscheidung ergänzen.**
   - Dateien: `scanner/opportunity_research.py`, `tests/test_opportunity_research_v24.py`.
   - Kurzfristige und mittelfristige Verfügbarkeitsfelder aus denselben Records liefern.
   - Bei fehlenden Kursen, Liquidität, Bewertung oder Trend ausschließlich `unavailable` ausgeben.

8. **Coverage, Evaluation und Benchmark ausführen.**
   - Dateien: `scanner/research_index/evaluation.py`, `benchmarks/research_v24.py`,
     `docs/research-v24-coverage.json`, `docs/research-v24.md`.
   - Recall@10/50, Top-1/3, PIT, Enthaltung, Coverage, p50/p95, Antwortgröße, Requests und Kosten
     reproduzierbar ausgeben; echte und synthetische Resultate deutlich trennen.

9. **Europäische Quellenentscheidung dokumentieren.**
   - Datei: `docs/research-v24-source-decision.md`.
   - Für jede Quelle Rechte, historische Zeitsemantik, technische Zugänglichkeit, Rate-Limits und
     Kosten belegen. Adapter nur nach positivem Ergebnis und innerhalb 20 EUR/Monat hinzufügen.

10. **Abschlussprüfung.**
    - `ruff check .`, `ruff format --check .`, vollständiges `pytest`, Docker-Build und Actions.
    - Index zweimal bauen und Datenbank-/Manifest-SHA vergleichen; Rückwärtskompatibilität von
      V2.3 Fixture/Cached-Modus prüfen. Kein Merge, Deployment oder produktive Migration.
