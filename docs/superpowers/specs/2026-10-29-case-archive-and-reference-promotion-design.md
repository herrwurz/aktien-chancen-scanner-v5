# Fallarchivierung und Referenzübernahme

## Zweck

Die Testfälle `TI-d2dbb1445c2dd2d9202a` und `TI-c49541d04ed87748f7b8` sollen aus der
aktiven Oberfläche und aus Qualitätskennzahlen verschwinden, ohne das verkettete Journal zu
verändern. Der aktuelle Fall `TI-22d214ce388b332dfbf9` (HEBELTRADER 201/26) bleibt als
prospektiver Blindtest aktiv und darf erst nach eingefrorener Erstprognose und belegter späterer
Auflösung als neuer Referenzfall übernommen werden.

## Verhalten

- Archivieren erzeugt ein neues append-only Ereignis; bestehende Ereignisse bleiben unverändert.
- Archivierte Fälle sind standardmäßig in „Meine Fälle“ ausgeblendet und aus Qualitätskennzahlen
  ausgeschlossen. Eine separate Ansicht kann sie weiterhin anzeigen.
- Nur ausdrücklich angegebene Fall-IDs dürfen archiviert werden.
- Eine Auflösung benötigt weiterhin Aktie, Herkunft der Auflösung, Fehleranalyse und optional die
  aus dem gekauften Bericht übernommene WKN.
- Nach der Auflösung kann der Betreiber den Fall ausdrücklich als Referenz freigeben.
- Fall 201/26 wird als `prospective_blind` gekennzeichnet. Seine Erstprognose bleibt unverändert.
- Der neue Eintrag wird getrennt von den 18 rekonstruierten Entwicklungsfällen als prospektiver
  Fall 19 ausgewiesen. Er wird nicht rückwirkend als unabhängiger Treffer gezählt, bevor eine
  Auflösung vorliegt.

## Umsetzung

- Neue Journalereignisse `archive` und `reference_promotion` mit Herkunft, Zeitpunkt und Begründung.
- Authentifizierte API-Aktionen und Schaltflächen in der Weboberfläche.
- Standardfilter für aktive Fälle sowie eine einblendbare Archivansicht.
- Qualitätsbericht ignoriert archivierte Fälle und unterscheidet Entwicklungsreferenzen von
  prospektiven Blindfällen.
- Regressionstests sichern Journalintegrität, unveränderte Erstprognose, Filterung und explizite
  Referenzübernahme.

## Erwogene Wege

- Physisches Löschen wurde verworfen, weil es die Hash-Kette und den Abnahmenachweis zerstört.
- Automatische Referenzübernahme wurde verworfen, weil ungeprüfte oder unvollständige Auflösungen
  sonst die Wissensbasis verunreinigen könnten.
- Gewählt wurde eine reversible Anzeige-Archivierung mit expliziter Referenzfreigabe.

## Grenzen

Die Änderung löscht keine Dateien und übernimmt keine gekaufte PDF in das öffentliche Repository.
PDF und Auflösungsbelege bleiben im privaten persistenten Hetzner-Speicher. Es erfolgt weder ein
Deployment noch ein Merge durch Codex.
