# HEBELTRADER Implementation Plan

**Goal:** Nachvollziehbarer lokaler PDF-Import als Grundlage historischer Analysen.
**Architecture:** Unterpaket `scanner/hebeltrader`, bestehende SQLAlchemy-Basis,
additive Alembic-Migration und optionaler Compose-Importservice.
**Tech Stack:** Python 3.12, pdfplumber, PostgreSQL, SQLAlchemy, pytest, ReportLab-Testdaten.
**Spec:** ../specs/2026-10-22-hebeltrader-design.md (vom Nutzer freigegeben).
**Execution:** Direkt auf `feat/hebeltrader-history`; abschließende unabhängige Prüfung.

## Global Constraints
- Kein produktives Deployment, keine Trades oder kostenpflichtigen Dienste.
- Keine Original-PDFs, Volltexte oder Zugangsdaten im Repository.
- Herkunftskategorien bleiben unverifiziert und werden nie als Outcomes verwendet.
- Fehlende/mehrdeutige Werte bleiben leer und werden zur Prüfung markiert.

## Review Focus
- Vermischung von Aktien- und Derivatwerten oder mehrerer Empfehlungen.
- Identische Ausgaben mit verschiedenen Namen, Kategorien oder Dokumentversionen.
- Scans/defekte PDFs, ungültige Zahlen, widersprüchliche Publikationsmetadaten.
- Veröffentlichungstag ohne Uhrzeit und Modellmerkmale mit Zukunftsinformationen.
- Optionaler Import darf bestehende Compose-Services nicht verändern.

## Task 1: Extraktion und Qualitätsprüfung
Files: `scanner/hebeltrader/{domain,pdf,parser}.py`, `tests/hebeltrader/`.
Interface: `extract_pdf(bytes) -> Extraction`, mit Seiten, Tabellen,
Empfehlungen, Feldbelegen und Prüfbefunden.
- [x] Synthetische PDF-Beispiele und Tests für Text/Tabellen, zwei Instrumente,
  mehrere Empfehlungen, deutsche Zahlen, Metadatenkonflikte und OCR-Bedarf schreiben.
- [x] Tests ausführen: fehlende Implementierung muss scheitern.
- [x] Belegorientierte Extraktion implementieren; keine Schätzung fehlender Daten.
- [x] Tests ausführen und committen.

## Task 2: Persistenz, Import, Analyseexport
Files: `scanner/hebeltrader/{models,importer,analysis,cli}.py`, Migration `0002`,
Anbindung der Metadaten in `scanner/models.py`.
Interfaces: `import_folder(sessions, root) -> summary`,
`export_features(session, as_of) -> list[dict]`.
- [x] Tests für SHA-Deduplizierung, Ausgabenidentität, Varianten, Belege,
  Dateifehlerisolation, Importbericht und konservativen zeitbezogenen Export schreiben.
- [x] Fehlende Funktionen im Testlauf nachweisen.
- [x] Additive Tabellen, transaktionalen Import und lesende Analysefunktionen implementieren.
- [x] SQLite-/PostgreSQL-Migrationsprüfung und Gesamtsuite ausführen, committen.

## Task 3: Betrieb und Prüfung
Files: Compose-Profil `analysis`, Locks, Dockerfile, README und `docs/hebeltrader.md`.
- [x] Optionales Read-only-Quellmount und getrennten Berichtspfad ergänzen.
- [x] CLI-Import und Wiederholungsimport im Container prüfen.
- [x] Autorisiert geladene Originalausgabe lokal prüfen, ohne Inhalte zu veröffentlichen.
- [x] Ruff, vollständige pytest-Suite, Compose und Image-Build prüfen.
- [x] Unabhängige Codeprüfung, erforderliche Regressionen und Testergebnisse dokumentieren.
- [ ] Feature-Branch pushen und Pull Request gegen main öffnen.
