# Teaser-Detektiv im Browser auf Hetzner

Die vorhandene Oberfläche unterstützt Text, öffentliche URL, Screenshot und PDF.
Neu: Schutz der gesamten Anwendung mit Browser-Passwort, gespeicherte Fälle öffnen,
serverseitiges Recherchetoken und ein separater HTTPS-Docker-Betrieb.
Keine kostenpflichtige KI oder Datenquelle wird aktiviert. Die Recherche verwendet
weiterhin öffentliche Quellen mit deren bekannten Einschränkungen; eine Weboberfläche
beseitigt keine Quellenlücken und garantiert keine Identifikation.

## Vor dem Start

Benötigt werden eine eigene Subdomain, ein DNS-A-Eintrag auf die Hetzner-IP und
Docker Compose. Ein vorhandener AAAA-Eintrag muss ebenfalls zum Server führen.
Ports 80 und 443 müssen frei und erreichbar sein. **Wenn bereits Immich oder ein anderer
Reverse Proxy diese Ports nutzt, dieses Compose-Paket noch nicht starten.** Den vorhandenen
Proxy nicht stoppen oder umkonfigurieren. Zuerst dessen Art und freie Anschlussmöglichkeit
klären; diese Anleitung verändert keine bestehende Proxy-Konfiguration.

Der neue Compose-Projektname ist `teaser-web`. Es gibt keinen Börsenworker und keine
Verbindung zur bestehenden PostgreSQL-Datenbank. Die Web-Anwendung verwendet ausschließlich
`deploy/teaser/state/web.db` und ihr eigenes Fall-/Quellenarchiv. Caddy erhält eigene
Zertifikatsvolumes. Die App selbst veröffentlicht keinen Host-Port.

## Konfiguration vorbereiten

Im separaten Checkout dieses PR-Branches:

```bash
cd /opt/aktien-chancen-scanner-v5
bash scripts/setup_teaser_web.sh
```

Das Skript fragt die Domain und zweimal ein neues Web-Passwort ab. Als Benutzer gilt
`admin`. Es legt nur neue Dateien in `deploy/teaser` an und startet keinen Container.
Vorhandene Konfiguration wird nicht überschrieben. Nicht das Tiingo-Passwort oder einen
API-Schlüssel als Web-Passwort verwenden.

Secrets liegen in ignorierten Dateien, nicht in Git oder im Image. Die App läuft als
UID/GID 10001. Die Passwort- und Token-Dateien sind root-eigen, gruppenlesbar für 10001;
das neue Datenverzeichnis gehört 10001. Das Recherchetoken wird automatisch erzeugt
und vom Server eingesetzt. Es muss nicht im Browser eingegeben werden.

## Bewusst starten – erst nach Prüfung der Ports und DNS

```bash
cd /opt/aktien-chancen-scanner-v5/deploy/teaser
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Dann `https://DEINE-DOMAIN` öffnen und mit `admin` und dem selbst vergebenen Passwort
anmelden. Caddy beschafft und erneuert das kostenlose HTTPS-Zertifikat automatisch.
Die erste Zertifikatsausstellung benötigt funktionierendes DNS und die offenen Ports.
Die Anmeldung gilt für Oberfläche und APIs. HTTPS ist für die Passwortübertragung zwingend.

Text einfügen oder Datei wählen, „Hinweise analysieren“ drücken. Die Recherche kann einige
Minuten dauern. Bei Verbindungsabbruch zuerst „Gespeicherte Fälle laden“ verwenden: Ein
serverseitig abgeschlossener Lauf kann bereits archiviert sein. Die Fallliste zeigt den
letzten Bericht; die Erstprognose bleibt im bestehenden Journal erhalten. Spätere Auflösungen
lassen sich weiterhin getrennt erfassen. Ungelöste Fälle werden ausdrücklich so angezeigt.

## Betrieb und Sicherung

```bash
cd /opt/aktien-chancen-scanner-v5/deploy/teaser
docker compose logs --tail=100 app https
docker compose stop
```

`stop` beendet nur dieses Compose-Projekt und behält Dateien und Volumes.
Für eine konsistente Sicherung nach `stop` das gesamte private Verzeichnis `state`,
`.env` und `secrets` sichern, anschließend `docker compose start`. Keine Zugangsdaten
oder hochgeladenen Börsenbriefe in Git einchecken. Passwortwechsel: Datei `secrets/password`
privat ersetzen, Berechtigungen 0440/root:10001 beibehalten und nur `app` neu starten.
Der Browser speichert HTTP-Basic-Anmeldedaten bis zum Schließen seiner Sitzung; es gibt
keinen zuverlässigen Logout-Knopf. Für gemeinsam genutzte Geräte ein privates Browserfenster
verwenden. Das Paket ist für einen einzelnen Betreiber gedacht, nicht für Mehrbenutzerbetrieb.

## Nachweis und Grenzen

Lokal geprüft: Authentifizierung auf UI/API, falsches Passwort, fehlende Secrets,
Cross-Origin-Schreibsperre sowie Eingabe, persistente Ablage und Wiederöffnung eines
Teasers. JavaScript-Syntax wird geprüft; keine vollständige Browser-Automatisierung.
Docker wird isoliert getestet. Kein Hetzner-Zugriff, keine echte Zertifikatsausstellung
und kein produktiver Start wurden durch Codex durchgeführt.

Zum realen Start fehlen noch die gewählte Domain, ihr DNS-Eintrag und die Prüfung,
wer auf dem Server Ports 80/443 belegt. Bestehende Proxy-/Immich-Dienste bleiben unberührt.

Prüfergebnis dieser Änderung: **766 lokale Tests bestanden, 8 PostgreSQL-Tests übersprungen**;
Ruff und JavaScript-Syntax erfolgreich. Der echte isolierte Docker-Prozess lieferte ohne
Anmeldung HTTP 401, mit Anmeldung eine erfolgreiche Teaser-Annahme und anschließend einen
persistierten Fall. `docker compose config --quiet` und Caddy-Konfigurationsvalidierung
waren erfolgreich. Der Docker-Lauf verwendete Dummy-Secrets und keine externen Rechercheabrufe.
