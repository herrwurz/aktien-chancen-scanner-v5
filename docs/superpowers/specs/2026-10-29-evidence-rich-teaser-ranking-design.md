# Aussagekräftiges Teaser-Ranking

## Ziel

Der Detektiv soll Kandidaten anhand tatsächlich gefundener, zitierbarer und unterscheidender
Belege sortieren. Ein Kandidat darf nicht allein wegen eines technischen Gleichstands auf Rang 1
erscheinen. Die Änderung darf ASML oder eine andere bekannte Lösung nicht fest einprogrammieren.

## Recherchepfad

1. Tavily Search liefert URL, Titel, Textabschnitt, Score und gemeldeten Creditverbrauch. Diese
   Daten werden unverändert mit Abrufzeit und Hash archiviert.
2. Der direkte öffentliche Abruf bleibt der bevorzugte Weg für Primärquellen.
3. Scheitert er an Robots, 403, JavaScript oder Dokumentgröße, wird Tavily Extract einmalig für
   den Treffer verwendet. Zugangsschranken und Logins werden nicht umgangen.
4. Bleibt auch Extract erfolglos, darf der archivierte Suchabschnitt als vorläufige Quellenklasse C
   verwendet werden. Er kann eine Hypothese stützen, aber keine automatische Identifikation allein
   bestätigen.

## Evidenz und Ranking

- Quellenklasse A: regulatorische oder direkt archivierte Unternehmensprimärquelle.
- Quellenklasse B: über Tavily Extract archivierter Inhalt einer Primärquelle.
- Quellenklasse C: Tavily-Suchabschnitt mit URL, Abrufzeit und Inhaltshash.
- Quellenklasse D: seriöse Sekundärquelle.
- Quellenklasse E: unbelegte Modellhypothese; zählt nicht als Beleg.
- Konkrete Unternehmensereignisse, exklusive Technologien, benannte Gegenparteien und exakte
  Kennzahlen erhalten höhere Spezifität als allgemeines Wachstum, Charttechnik und Werbesprache.
- Quellenqualität und Spezifität werden getrennt ausgewiesen. Das Modell liefert zitierte
  Zuordnungen; deterministischer Code berechnet die Rangfolge.
- Kandidaten ohne belegten spezifischen Hinweis werden nicht als eindeutiger Rang 1 dargestellt.
- Bei Evidenzgleichstand lautet der Status `ambiguous_tie`; die Anzeige erklärt den Gleichstand.

## Kosten und Grenzen

- Tavily Basic Search bleibt Standard; Extract wird gebündelt und nur bei gescheitertem Abruf
  eingesetzt.
- Provider-Credits und OpenAI-Tokens werden aus den Antworten erfasst.
- Monatsbudget und deaktivierte automatische Aufladung bleiben unverändert.
- Suchabschnitte werden nie als Primärquellen bezeichnet; unklare Publikationszeiten bleiben
  zeitlich unsicher.

## Abnahme

- Ein blockierter, relevanter Treffer bleibt über Extract oder Suchabschnitt im Bericht sichtbar.
- Eine Rechercheplattform oder ein Herausgeber wird nicht zur Aktie.
- Belegte technologische Unersetzbarkeit schlägt bloß allgemeine starke Finanzzahlen.
- Ein reiner Scoregleichstand erzeugt keinen scheinbaren Sieger.
- Ausgabe 201/26 wird anschließend neu ausgeführt; ihr Ergebnis bleibt eine Hypothese bis zur
  gekauften Auflösung.
