#!/usr/bin/env bash
set -euo pipefail
# Configuration only: never starts Docker or changes existing proxy configuration.
if [ "$(id -u)" -ne 0 ]; then
  echo 'Bitte als root ausführen, damit nur die neuen Scanner-Dateien korrekt berechtigt werden.' >&2
  exit 1
fi
teaser_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../deploy/teaser" && pwd)
cd "$teaser_dir"
if [ -e .env ] || [ -e secrets ]; then
  echo 'Vorhandene Konfiguration bleibt unverändert. Siehe docs/teaser-web-hetzner.md.' >&2
  exit 1
fi
read -rp 'Gewünschte Domain (z.B. teaser.example.at): ' teaser_domain
if [[ ! "$teaser_domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || [[ "$teaser_domain" != *.* ]]; then
  echo 'Bitte nur einen vollständigen Domainnamen ohne https:// oder Pfad eingeben.' >&2
  exit 1
fi
read -rsp 'Neues Web-Passwort (mindestens 12 Zeichen): ' teaser_password
printf '\n'
read -rsp 'Passwort wiederholen: ' teaser_repeat
printf '\n'
if [ "${#teaser_password}" -lt 12 ] || [ "$teaser_password" != "$teaser_repeat" ]; then
  unset teaser_password teaser_repeat
  echo 'Passwörter müssen übereinstimmen und mindestens 12 Zeichen lang sein.' >&2
  exit 1
fi
umask 077
mkdir secrets
mkdir -p state
printf '%s' "$teaser_password" > secrets/password
unset teaser_password teaser_repeat
python3 -c 'import secrets; print(secrets.token_urlsafe(48), end="")' > secrets/token
printf 'TEASER_DOMAIN=%s\nTEASER_USERNAME=admin\n' "$teaser_domain" > .env
chown 0:10001 secrets/password secrets/token
chmod 440 secrets/password secrets/token
chown 10001:10001 state
chmod 700 state
echo 'Konfiguration angelegt. Es wurde kein Dienst gestartet.'
echo 'DNS, Ports und Startbefehl: docs/teaser-web-hetzner.md'
