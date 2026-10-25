# Scanner V6 V2.5.2 – Candidate Generation (Spezifikation)

## Umfang

V2.5.2 liest ausschließlich den V2.4-Research-Index und ein akzeptiertes V2.5.1-Kursarchiv. Es
erzeugt Research-Kandidaten für 1–20 Handelstage, aber keine Orders und keine als verifiziert
bezeichneten Kaufsignale. Der HEBELTRADER-Detektiv bleibt ein getrenntes Entscheidungsmodell.

## Komponenten

- `scanner/opportunities/features.py`: ausschließlich vergangenheitsgerichtete 5-/10-/20-
  Sitzungsrendite, Volumenratio gegen 20 abgeschlossene Vorgängersitzungen, ATR, Gap-Risiko,
  Median-Dollarumsatz und relative Stärke.
- `scanner/opportunities/catalysts.py`: point-in-time verfügbare PRIMARY-/SECONDARY-Ereignisse;
  COMMUNITY nur als Zusatzsignal.
- `scanner/opportunities/short_term.py`: harte Daten-Gates und nachvollziehbares Ranking.
- `scanner/opportunities/cli.py`: read-only Dry-run mit JSON-/CSV-Audit.

## Daten-Gates

Erforderlich sind exakte Aktienidentität, mindestens 250 belegte Sitzungen, rohe und adjustierte
Reihe, Actions, Währung, MIC, Zeitstempel und ausreichende Liquidität. Ein unabhängiger Kalender
oder explizite Coverage-Lücke ist Pflicht. Ohne beobachtete Quotes bleibt Spread `unavailable`;
ein separates konservatives Kostenband darf kein beobachtetes Bid/Ask vortäuschen.

Ein Kandidat braucht einen belegten Katalysator oder ein vorab definiertes Preis-/Volumenereignis.
Fehlende Pflichtdaten ergeben `unavailable`, widersprüchliche oder knappe Evidenz `watch_only`.
Rankingwerte heißen nicht Wahrscheinlichkeit.

## Tests und Abnahme

- keine Verwendung der Signal- oder Folgesitzung in Lookbacks;
- Split/Dividende verändert rohe und adjustierte Merkmale nachvollziehbar;
- Fonds, Identitätskonflikte und veraltete Daten werden ausgeschlossen;
- ein später abgerufener/korrigierter Datensatz erscheint nicht im strikten historischen Lauf;
- Katalysator nach Signalzeitpunkt wird ausgeschlossen;
- fehlende Quote kann kein ausführbares CRV erzeugen;
- mindestens zehn echte, unabhängig ausgewählte Titel mit dokumentierter Coverage;
- Laufzeit, Kosten, Enthaltungen und False-Positive-Prüfliste im Bericht.

V2.5.2 beginnt erst, wenn ein realer V2.5.1-Pilot zehn Titel mit ausreichender Historie archiviert
hat. Der PR enthält keinen historischen Performanceanspruch.
