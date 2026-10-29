# Kompakte Teaser-Fallansicht

## Zweck
Die mobile Teaser-Oberfläche soll gespeicherte Fälle ohne lange Liste bedienbar machen, den laufenden Analysestatus unübersehbar anzeigen und die Eingabe einer späteren Originalauflösung in den normalen Fallablauf integrieren.

## Gewählter Ansatz
Eine Combobox wählt genau einen gespeicherten Fall aus. Darunter erscheint nur dessen kompakte Einzelansicht mit Bericht und passenden Aktionen. Historische Referenzen bleiben eingeklappt. Alternativen waren eine vollständige Akkordeonliste und eine filterbare Tabelle; die Einzelansicht wurde wegen der besseren mobilen Bedienbarkeit gewählt.

## Verhalten
- „Meine Fälle“ enthält Auswahl, Laden/Aktualisieren und einen einzigen aktiven Fall.
- Archivierte Fälle lassen sich über einen Filter einbeziehen, ohne eine zweite lange Liste zu erzeugen.
- Während einer Analyse erscheint direkt beim Formular eine kräftige rote Statusbox und der Analyseknopf zeigt den laufenden Zustand.
- Fehler zeigen HTTP-Status und sichere Serverdetails sichtbar in derselben Statusbox.
- Beim aktiven Fall und nach einer neuen Analyse steht ein prominenter Button „Originalauflösung eintragen“.
- Der Button öffnet den Auflösungsbereich, übernimmt Fall-ID und bekannte Aktienidentität soweit verfügbar und scrollt zum Formular.
- Die append-only Fall- und Auflösungslogik sowie API-Verträge bleiben bestehen.

## Grenzen
Keine Änderung an Ranking, Recherche, Referenzdaten oder Produktivdaten. Keine automatische Auflösung und keine Wertpapieraktion.
