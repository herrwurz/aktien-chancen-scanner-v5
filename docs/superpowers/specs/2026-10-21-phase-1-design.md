# Phase 1: Technisches Fundament

Freigegebene Grundlage: Architekturvorschlag im Chat, bestätigt mit „Dann ja mache“.

Python 3.12, FastAPI und ein eigenständiger Scheduler-Prozess verwenden PostgreSQL
über SQLAlchemy. Alembic verwaltet das Schema. API und Dashboard sind ausschließlich
lesend; nur der Worker importiert Daten. Die Oberfläche bindet standardmäßig an
127.0.0.1:8066. PostgreSQL veröffentlicht keinen Host-Port. Compose-Projekt
`chancen-scanner-v6` besitzt eigene Netzwerke und ein eigenes Datenvolume.

Eine gemeinsame Provider-Schnittstelle liefert normalisierte OHLCV-Kerzen mit
Assetklasse, Anbieter, Symbol, Zeitraster, UTC-Zeitstempeln und Decimal-Werten.
Binance Spot verwendet öffentliche Marktdaten ohne Schlüssel. Ein Fixture-Provider
ermöglicht einen reproduzierbaren Offline-Durchlauf. Aktien, DEX und Community
erhalten Erweiterungspunkte, aber keine vorgetäuschte produktive Implementierung.

Der Worker scannt konfigurierbare Symbole in 5m und 15m. Er verarbeitet nur
abgeschlossene Kerzen und wertet jede importierte Kerze mit ausschließlich früheren,
lückenlosen Kerzen aus. Standard: 20 Vergleichskerzen, mindestens 3-faches
Basisvolumen und 100000 Quote-Volumen. Jede Entscheidung enthält Messwerte,
Algorithmusversion, Kerzenbezug, Ablehnungsgrund und tatsächlichen Auswertungszeitpunkt.
Wiederholte Imports erzeugen keine doppelten Kerzen oder Entscheidungen.

PostgreSQL sperrt gleichzeitige Worker-Durchläufe per Advisory Lock. Fehler eines
Symbols blockieren die übrigen Symbole nicht. HTTP-Anfragen haben Zeitlimits und
begrenzte Wiederholungen. Laufstatus und Fehleranzahl sind sichtbar.

Das Schema reserviert eine Outcome-Tabelle für spätere 1h/4h/24h-Auswertungen.
Outcome-Berechnung, Nachrichten, Bitpanda-Verifikation und Paper-Portfolio sind
Folgephasen. Signale sind Beobachtungen, keine ausführbaren Empfehlungen.
Es gibt weder Order-Endpunkte noch Trading-Schlüssel. DOOD/ZEREBRO werden mangels
historischer Belege nicht als validierte Fälle bezeichnet.

pytest prüft Signallogik einschließlich Zeitbezug und Datenlücken, HTTP-Parsing und
Fehler, wiederholte Persistenz, lesende API, Migrationen und Compose-Isolation.
PostgreSQL wird zusätzlich real geprüft, sofern Docker verfügbar ist.
