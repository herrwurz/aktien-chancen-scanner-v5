# HEBELTRADER – ausgeführte Prüfungen

Stand: 22.10.2026. Ausschließlich isolierte Entwicklungs-/Testressourcen,
kein produktives Hetzner-Deployment. Lokal Python 3.12.14, im Image Python
3.12.12, PostgreSQL 17.6 in einem eigens angelegten Testcontainer.

## Automatisiert

```text
TEST_DATABASE_URL=<wegwerfbare PostgreSQL-Datenbank> python -m pytest -q
81 passed

ruff check .
All checks passed!

ruff format --check .
39 files already formatted

git diff --check
Exit 0

python -m pip check
No broken requirements found.
```

Die Gesamtsuite enthält unverändert die vorhandenen Scanner-Tests. Drei
PostgreSQL-Tests werden ohne `TEST_DATABASE_URL` übersprungen; der dokumentierte
vollständige Lauf verwendete PostgreSQL und hatte keine übersprungenen Tests.
Unix-Dateirechtetests werden bei einem Testlauf als root übersprungen; der
ausgeführte Lauf erfolgte als nicht privilegierter Benutzer.

Geprüft sind Text-/Tabellenextraktion aus synthetischen PDFs, getrennte Aktien-
und Derivatwerte sowie Basispreis-/Optionspreiswährungen, mehrere Empfehlungen,
gemischte Abschnitte auf einer Seite, deutsche Decimal-Werte, fehlende/ungültige
Felder und Kennungen, Metadatenkonflikte und ungültige Publikationsdaten,
Scan-/defekte Dateien, Originalbytes, Feldbelege, Kopien/Umbenennungen,
Variantenkonflikte, CLI-Berichte, Freigaben, Ablehnungen und zeitbezogene Exporte.
Unlesbare Quellen und Unterordner werden ausdrücklich als Fehler behandelt.

Die Migration `0002` wurde auf SQLite und PostgreSQL geprüft, einschließlich
Alembic-Driftprüfung und Upgrade-/Downgrade-Roundtrip. Ein separater Test belegt,
dass bestehende Scanner-Daten bei Upgrade von `0001` erhalten bleiben.

## Image und optionaler Compose-Service

- Docker-Build erfolgreich; öffentliche CA des Entwicklungsproxies nur als
  temporäres BuildKit-Secret, keine Zugangsdaten oder Original-PDFs im Image.
- `docker compose --profile analysis config --quiet` erfolgreich.
- Eigenes Testprojekt `chancen-scanner-v6-hebel-smoke`, ausschließlich dessen
  Datenbank, Migration und expliziter Importservice gestartet.
- Migration im Image mit Benutzer UID 10001 erfolgreich.
- Container-Import aus schreibgeschütztem Testordner: drei synthetische Dateien,
  zwei verschiedene Originalbytes, eine Kopie; **2 neu importiert, 1 übersprungen,
  2 Empfehlungen, 0 Fehler**.
- Wiederholungsimport: **0 neu importiert, 3 übersprungen, 0 Fehler**.
- JSON-Berichte wurden über den gesonderten Berichtsmount geschrieben.
- Der erste Smoke-Versuch erkannte fehlende Leserechte der Testquelle. Die
  Dateisuche wurde daraufhin mit Regressionstests gegen stilles Überspringen
  unlesbarer Ordner abgesichert; mit passenden Rechten wurde der Import wiederholt.

## Autorisierte Originalprüfung

Eine sechsseitige Originalausgabe wurde über den bereits verbundenen,
autorisierten Google-Drive-Connector lokal geladen und mit dem finalen Parser
gegen die separate PostgreSQL-Testdatenbank importiert. Ergebnis: eine Ausgabe,
eine Empfehlung, keine Dateifehler. Ein zweiter Import erzeugte kein Duplikat.
Aktien- und Derivatkennungen sowie Preise wurden getrennt gegen die Original-
angaben geprüft. Der nicht ausdrücklich vorhandene Emittent blieb `NULL` und
wurde markiert. Die Empfehlung blieb `pending`, keine automatische Freigabe.

Originaldatei, Volltext und private Berichte sind nicht Teil des Repositorys.
Alle eingecheckten PDF-Beispiele sind synthetisch.

## Codeprüfung und Grenzen

Eine unabhängige lesende Prüfung fand drei relevante Randfälle. Für jeden wurde
zuerst ein fehlschlagender Regressionstest ausgeführt, dann die Ursache behoben:

1. Basispreis-Währung und Derivat-Handelswährung werden getrennt gespeichert.
2. Varianten benötigen quellspezifische Verfügbarkeitszeit und Beleg, bevor sie
   historische Features liefern; die ursprüngliche Publikationszeit wird nicht
   blind auf spätere Varianten übertragen.
3. Ausgabenidentität bleibt auch bei ungültigem Datum erhalten, damit Konflikte
   eine frühere Freigabe tatsächlich zurücksetzen.

Zusätzliche Hinweise zu unklassifiziertem Eröffnungstext, gemischten Abschnitten
und Compose-Isolation wurden ebenfalls durch Implementierung/Tests berücksichtigt.

Nicht durchgeführt: vollständiger Import/Qualitätsabgleich sämtlicher 118
Original-PDFs, OCR, produktive Migration, Rendite-/Erfolgsberechnung oder
Trainings-/Backtest-Validierung. Ein JSON-Export ist eine quellenbezogene
Datengrundlage, kein nachgewiesenes Handelssystem. Die CI-Ausführung auf GitHub
ist getrennt vom hier dokumentierten lokalen Ergebnis zu beurteilen.
