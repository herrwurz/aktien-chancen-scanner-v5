# V2.5.2 – realer Dry-run-Status

Stand: 25. Oktober 2026.

Der echte V2.5.1-Hetzner-Pilot ist `partial`: 10 ausgewählte Titel, 9 importierte Reihen, davon
acht mit 250 Zeilen, PXED mit 58 Zeilen und VOGX mit Providerfehler. Zusatzkosten und neue Requests
des V2.5.2-Scans betragen 0.

Der V2.5.2-Code und sein offline ausführbarer Serverlauf sind fertig. In der Codex-Umgebung war das
Hetzner-Archiv nicht verfügbar. Daher werden noch keine echten Kandidatenzahlen, Scores oder
Risikowerte behauptet. Nach dem Serverlauf gehören hier nur die Coverage-Zahlen und der SHA-256 des
Berichts hinein; lizenzierte Rohkurse bleiben auf dem Server.

Der Runner prüft nun vor dem Lauf den V2.5.1-Coverage-SHA, den logischen Archiv-SHA, getrennte
Ein-/Ausgabepfade und einen vollständig netzlosen Container. Der weiterhin ausstehende reale Lauf
ist ein externer Abnahmeblocker für PR #22; erfolgreiche Regressionstests ersetzen ihn nicht.

Abnahme bleibt `limited_modeled_research`, selbst wenn alle acht Reihen technisch ausgewertet
werden. Gründe sind der fehlende unabhängige Börsenkalender, ein fehlender belegter Marktbenchmark,
keine historischen Bid-/Ask-Quotes und die erst 2026 erfolgte lokale Archivierung.
