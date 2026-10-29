# 18 Referenzfälle – Abgleich, Trennung und gezieltere Recherche

Eigener Branch/PR auf PR #29 (7483e28); keine Merges oder Deployments.

1. Alle Nutzerdaten in `data/hebeltrader/teaser-cases.json` versionieren; nur genau diese
   Datei von der bisherigen data-Ignore-Regel ausnehmen. Alte HT-IDs erhalten und die
   neue Nutzernummerierung separat speichern. Williams-Auflösung null. 17 vollständige
   Texte fehlen; ADI-Originaltext exakt übernehmen. Auflösungshinweise getrennt von
   tatsächlich im Teaser enthaltenen Hinweisen führen. Alte Prognosewerte nur als
   historische, unkalibrierte Angaben archivieren.
2. JSON-Lader/Exporter/Evaluator separat: Scanexport nur ID, Überschrift, Originaltext und
   Zeitmetadaten. Keine Aktie, WKN, Erstprognose, Fehleranalyse oder Lösungs-Hinweise im
   Scanexport. Evaluator liest Lösungen erst nach SHA-Prüfung eingefrorener Rankings.
   Bekannte Fälle bleiben immer Entwicklungsregressionen; Original-Top3 und Uhrzeiten
   nicht rekonstruieren. Docker-Scan erhält nur exportierte Eingaben/Quellenpaket und
   Ausgabe; Referenzsammlung/Markdown/PDFs/Labels werden nicht ins Image kopiert.
3. Zentrale Markdown-Tabelle zusammenhängend und mit JSON synchronisieren. Alte Fassung
   separat als datierte Provenienz sichern; Änderungen/neu ergänzte Ersttipps, Datierungen
   und Grenzen im Änderungsjournal nennen. Veraltete Behauptung „alle Originaltexte fehlen“
   im aktuellen Inventar korrigieren; alte Abnahme-Snapshots nicht still ändern.
4. Rechercheverbesserung nur aus Teaserinhalt: Akquisitionen plus unterschiedliche
   Geschäftsfelder und passende Finanzmerkmale als englisch/deutsche Suchqueries vor
   Marketingfloskeln. Keine bekannten Gewinner, Übernahmenamen aus Lösungen oder WKNs
   in Queries einschleusen. Frühen Abbruch nach acht ungeprüften Namen entfernen.
   Jeden vorläufigen Top-3-Kandidaten aktiv falsifizieren und veränderte Top3 markieren.
5. Tests zuerst für Schema/Lücken/Bilanz, Export-Whitelist, Lösungssperre, keine
   Auflösungsnamen im ADI-Input, generische Suchstrategie und Top3-Gegenprüfung. Alle 18
   Eingaben reproduzierbar offline testen: ohne datierte Unternehmensbelege Enthaltung,
   keine erfundenen erfolgreichen Identifikationen. Separater Bericht über 10/7/1 als
   Nutzerhistorie und über neue Regressionsergebnisse/fehlende Quellen.
6. Vollständige Suite, Ruff, isolierter Docker-Einzellauf, Review, eigener Draft-PR und
   konkrete Liste fehlender Texte/Zeiten/Primärbelege. Die reale ungelöste Ausgabe199 bleibt
   außerhalb dieser bekannten 18; keine neue Trefferquote ohne spätere belegte Auflösung.
