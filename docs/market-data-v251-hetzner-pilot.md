# V2.5.1 – realer Hetzner-Tiingo-Pilot

Stand: 25. Oktober 2026. Dieser Bericht dokumentiert den vom Nutzer im isolierten
Hetzner-Testverzeichnis ausgeführten Lauf. Die vollständigen maschinenlesbaren Artefakte bleiben
wegen der Tiingo-Nutzungsgrenzen auf dem Server; weder Provider-Rohdaten noch Zugangsdaten werden
in Git übernommen.

## Integritätsnachweis

- Coverage-JSON SHA-256: `fe243a487153ed89e5a019bb4df1216c5abd8259e75abe84c8dd4b66d824576f`
- `sha256sum -c coverage.sha256`: `coverage.json: OK`
- Auswahl: 10 reale US-Titel aus dem zuvor erzeugten und SHA-geprüften SEC-Universe-Archiv
- Tiingo-Requests: 10
- deklarierte und tatsächliche Zusatzkosten: 0 EUR
- Gesamtstatus: `partial`
- erfolgreich importiert: 9 von 10
- unabhängiger Börsenkalender: nicht vorhanden; keine Sitzungen wurden aus Wochentagen erfunden

## Abdeckung

| Ticker | Status | Sitzungen | Kalenderstatus |
| --- | --- | ---: | --- |
| FIVE | imported | 250 | unavailable_not_inferred |
| PXED | imported | 58 | unavailable_not_inferred |
| VOGX | provider_data_error | 0 | unavailable_not_inferred |
| MPAA | imported | 250 | unavailable_not_inferred |
| LEGN | imported | 250 | unavailable_not_inferred |
| RFL | imported | 250 | unavailable_not_inferred |
| INVE | imported | 250 | unavailable_not_inferred |
| BGM | imported | 250 | unavailable_not_inferred |
| AAPL | imported | 250 | unavailable_not_inferred |
| NC | imported | 250 | unavailable_not_inferred |

PXED belegt eine echte, aber für das angeforderte Fenster unvollständige beziehungsweise kürzere
Reihe. Für VOGX wurde keine Reihe erfunden oder ersatzweise über ein ähnlich benanntes Instrument
bezogen; der Providerfehler bleibt zur Identitäts- und Symbolprüfung offen.

## Bewertung

Der Lauf belegt den vollständigen technischen Weg von einer real archivierten SEC-Identität über
den begrenzten Tiingo-Abruf bis zum SHA-gebundenen Raw-, Revisions- und Coverage-Archiv. Der Status
`partial` ist deshalb ein erfolgreicher Integrationsnachweis, jedoch keine Behauptung vollständiger
Markthistorie.

Offen bleiben:

- unabhängiger, historisch belegter Handelskalender einschließlich Feiertagen und Early Closes;
- Ursache und gegebenenfalls historische Symbolzuordnung des VOGX-Fehlers;
- zeitliche beziehungsweise Listing-Ursache der nur 58 PXED-Sitzungen;
- vollständige Delisting- und Tickerwechselabdeckung.

Diese Punkte begrenzen spätere wissenschaftliche Backtests, blockieren aber nicht den Merge von
V2.5.1 als Infrastruktur-Inkrement. V2.5.2 darf die beiden eingeschränkten Titel nicht als
vollständig verfügbare Trainingsgrundlage behandeln.
