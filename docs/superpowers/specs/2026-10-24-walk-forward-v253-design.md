# Scanner V6 V2.5.3 – Walk-forward Backtest (Spezifikation)

## Ziel und Voraussetzungen

V2.5.3 bewertet die in V2.5.2 eingefrorene kurzfristige Strategie ohne Lookahead. Voraussetzung
sind akzeptierte Preis-, Kalender-, Action-, Identitäts- und Ereignis-Coverage sowie vor dem Test
festgelegte Kostenannahmen. Optionsscheinrenditen und HEBELTRADER-Regeln gehören nicht in diesen
Aktien-Backtest.

## Zeitmodell

Entwicklung, Schwellenwahl und Test werden in chronologisch getrennte, rollierende Fenster
geteilt. Das Universum wird für jedes Fenster point-in-time rekonstruiert; Delistings dürfen nicht
nachträglich entfernt werden. Nur bis zum Signalzeitpunkt tatsächlich bekannte Revisionen werden
verwendet. Ein Schlusskurssignal wird frühestens in der nächsten belegten Sitzung ausgeführt.

Tageshoch/-tief der Ausführungssitzung dürfen die Einstiegsentscheidung nicht beeinflussen.
Berühren Ziel und Stopp innerhalb derselben späteren Tageskerze, gilt konservativ der Stopp zuerst.
Die Höchsthaltedauer zählt belegte Handelssitzungen, nicht Kalendertage.

## Kosten und Benchmarks

Provision, Slippage und beobachteter Spread werden getrennt ausgewiesen. Ohne Quote werden mehrere
vorab festgelegte Kostenbänder gerechnet und ausdrücklich als Annahmen bezeichnet. Benchmarks sind
Buy-and-hold des belegten Marktindex, eine einfache 20-Sitzungs-Momentumregel und eine
liquiditätsgematchte Zufallsauswahl mit vorab fixiertem Seed.

## Kennzahlen und Abnahme

Coverage, Trefferquote, Nettoertrag, Maximum Drawdown, erwarteter Wert, Haltedauer, Turnover,
Kostenanteil, Fehlalarme und verpasste Chancen werden je Fenster und aggregiert berichtet. Zusätzlich
werden Stabilität nach Marktregime, Branche und Liquiditätsgruppe sowie Konfidenzintervalle gezeigt.

Abnahmetests erzwingen unveränderliche Eingabe-SHAs, zeitlich korrekte Revisionen, ausgeschlossene
Folgedaten, Corporate-Action-Behandlung, konservative Same-bar-Reihenfolge und reproduzierbare
Resultate. Ein positives Ergebnis darf erst nach einem vollständig unangetasteten Out-of-sample-
Fenster als Forschungsbefund bezeichnet werden; es bleibt keine Renditezusage und keine Order.
