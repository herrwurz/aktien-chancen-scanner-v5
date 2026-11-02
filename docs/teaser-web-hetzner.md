# Teaser-Detektiv im Browser auf Hetzner

Die vorhandene Oberfläche unterstützt Text, öffentliche URL, Screenshot und PDF.
Neu: Schutz der gesamten Anwendung mit Browser-Passwort, gespeicherte Fälle öffnen,
serverseitiges Recherchetoken und ein separater HTTPS-Docker-Betrieb.
Keine kostenpflichtige KI oder Datenquelle wird aktiviert. Die Recherche verwendet
weiterhin öffentliche Quellen mit deren bekannten Einschränkungen; eine Weboberfläche
beseitigt keine Quellenlücken und garantiert keine Identifikation.

## Vor dem Start

Gewählte Adresse: **https://teaser.hofreither.at**.

Benötigt werden diese Subdomain, ein DNS-A-Eintrag auf die Hetzner-IP und
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

Dann `https://teaser.hofreither.at` öffnen und mit `admin` und dem selbst vergebenen Passwort
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

## Coolify mit bereits vorhandenem Traefik

Keinen zusätzlichen Caddy starten. In der eigenen Coolify-Anwendung Build Pack Dockerfile,
Branch `feat/teaser-web-hetzner`, Base Directory `/`, Dockerfile `/Dockerfile`,
Domain `https://teaser.hofreither.at`, Ports Exposes `8000`, keine Ports Mappings.

Eigenes Bind-Mount-Verzeichnis auf Hetzner vorbereiten:

```bash
install -d -m 700 -o 10001 -g 10001 /opt/teaser-web-data
```

Coolify Persistent Storage: Directory/Bind Mount, Source `/opt/teaser-web-data`,
Destination `/data`. Keine Immich- oder bestehenden Datenbankverzeichnisse verwenden.

Runtime Environment Variables (nicht Build Variables):

```text
SCANNER_APP_FACTORY=scanner.web:create_web_app
TEASER_USERNAME=admin
TEASER_STATE_DIR=/data
TEASER_PASSWORD_FILE=/data/private/password
TEASER_TOKEN_FILE=/data/private/token
DETECTIVE_PUBLIC_ALLOW_NETWORK=true
DETECTIVE_PUBLIC_MAX_REQUESTS=40
```

Vor dem Start müssen die privaten Dateien `password` und `token` im Unterverzeichnis
`/opt/teaser-web-data/private` angelegt werden, für UID 10001 lesbar. Passwort mindestens
12 Zeichen; Token zufällig generieren. Keine geheimen Werte in Screenshots zeigen.
Fehlende Dateien verhindern den Start der geschützten Web-App. Coolify übernimmt
TLS und Routing. Keine zusätzlichen Ports oder Änderungen am bestehenden Proxy erforderlich.

## Historische Referenzfälle anzeigen

Nach Aktualisierung der Anwendung erscheint unter „Meine Fälle“ der separate Abschnitt
„Historische Referenzfälle“. Einmal „18 Referenzfälle laden“ drücken. Der Server lädt
nur die fest auf Commit `656d7ba` fixierte öffentliche Referenzdatei herunter, prüft deren
SHA-256 und archiviert sie unverändernd im eigenen `/data/references`-Verzeichnis.
Erneutes Laden verwendet das geprüfte lokale Archiv. Ohne Anmeldung kein Zugriff;
fehlgeschlagene Downloads verändern weder Falljournal noch Referenzbestand.

Angezeigt werden die 18 Überschriften, ursprünglicher Tipp, gemeldete Auflösung,
Call-WKN, Fehleranalyse und verfügbarer Originaltext. HT-016 Williams ist aus dem
aktiven Register entfernt.
10 richtig / 7 falsch / 1 ungelöst bezeichnet ausschließlich die rekonstruierte
Gesprächshistorie. Der Import erzeugt keine neuen Erstprognosen, keine Research-Kandidaten
und keine neuen Blindtest-Treffer. Die Rankingsuche liest diese Bibliothek nicht.
Für isolierte Blindtests weiterhin nur bereinigte Eingaben in den Scannercontainer mounten.
