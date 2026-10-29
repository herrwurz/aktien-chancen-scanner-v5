# Teaser 198/26 – Diagnose des leeren Web-Ergebnisses

Die vom Betreiber gemeldete Fall-ID ist `TI-d2dbb1445c2dd2d9202a`. Bekannte historische
Auflösung: SLB. Die frühere Identifikation wurde manuell mit gezielter breiter Webrecherche
und Unternehmensquellen erstellt; der automatisierte Detektiv hat diesen Nachweis bislang
nicht reproduziert. Eine alte richtige Lösung wird nicht in neue Rankings eingefügt.

## Reproduzierter Engpass

Ein tatsächlicher Test der eingebauten öffentlichen Recherche mit den Begriffen
`AI data center cooling oilfield services digital recurring revenue` ergab:

- Bing-RSS: `robots denied or unavailable` nach erfolgreichem Abruf von robots.txt.
- AKTIONÄR-RSS: robots.txt und Feed erreichbar (HTTP 200), aber null passende Treffer.
- Damit keine breite funktionierende Websuche und keine daraus erzeugbaren Gegenkandidaten.

Dies ist ein Lauf in der Codex-Umgebung, kein behaupteter Hetzner-Lauf. Die Fehler des
Betreiberlaufs müssen aus dessen gespeichertem `latest_prediction.research_errors` und
`discovery_source_gaps` separat geprüft werden. Das schmale aktuelle RSS-Fenster ersetzt
keine weltweite historische Recherche. Keine robots-Sperre wird umgangen.

## Korrektur

Ein Online-Lauf ohne Kandidaten wurde irreführend als `not_performed_offline` markiert.
Jetzt lautet der Falsifikationsstatus `not_performed_no_candidates`. Gibt es zusätzlich
Quellenfehler, steht in der Entscheidung `research_unavailable` / „Recherche derzeit nicht
verfügbar“. Eine erfolgreiche leere Suche bleibt von diesem Fehlerstatus unterschieden.
Echte Offline-Läufe behalten ihren korrekten Offline-Status.

JSON und Oberfläche zeigen Recherchemodus, Dokumentanzahl, Dokumente mit Firmenzuordnung,
Quellenfehler und den verbleibenden Requestrahmen. Ein JSON-Download hilft bei der
Betreiberdiagnose. Der passwortgeschützte Endpunkt `/api/hebeltrader/runtime` zeigt die
wirksame Netzfreigabe, Requestlimit, Suchprovider und konfigurierte Feeds; keine Secrets.
Dies ist Konfiguration, kein behaupteter Nachweis externer Erreichbarkeit.

Diese Korrektur repariert die Diagnose, nicht die fehlende breite Suchversorgung. Eine
zulässige, tatsächlich verfügbare breite Suchquelle und zuverlässige Zuordnung öffentlicher
Unternehmensquellen sind weiter erforderlich, bevor eine automatische SLB-Erkennung
zugesichert werden kann. Die Eingabe eines Publikationsdatums allein löst das Quellenproblem
nicht. Kein erfundener Treffer und keine neue Trefferquote werden ausgegeben.

## Aktivierung

Der Betreiber hat die Aktivierung autorisiert. In der Codex-Umgebung sind laut geprüfter
Runtime-Konfiguration keine Coolify-/SSH-Zugangsdaten oder entsprechenden Verbindungen
vorhanden. Es wurde kein Remote-Deployment ausgeführt.

In der bestehenden Coolify-Teaser-Anwendung ausschließlich den Git-Branch auf
`feat/hebeltrader-strategy-evidence` setzen, speichern und nach grüner CI deployen.
Domain, privates `/data`-Mount und bestehende Runtime-Secrets unverändert lassen.
Anschließend im angemeldeten Browser `/api/hebeltrader/runtime` prüfen: `public_research_enabled`
und `source_diagnostics_supported` müssen `true` sein. Den Teaser erneut analysieren;
die alte Erstprognose bleibt im Journal unverändert, eine Neubewertung wird angehängt.

Falls das Ergebnis erneut leer ist, dessen Quellenfehler prüfen. Ein erfolgreicher
Containerstart ist keine Abnahme erfolgreicher Teaseridentifikation.

## Bestätigung durch tatsächlichen Hetzner-Bericht

Der Betreiber lieferte den JSON-Bericht für Lauf `4dfd347f99a54f319b1c425d4d03b7be`,
analysiert am 28.10.2026 um 22:47:36 UTC. Dieser bestätigt `public_web`, die neuen
Recherchefragen sowie den korrigierten Status `not_performed_no_candidates`.
Die neue Version ist also bereits aktiv; ein falscher Branch oder deaktiviertes Netz
ist für diesen Lauf nicht die Ursache.

Es gab vier Requestversuche, 36 Requests waren noch frei. Bing-RSS war gesperrt.
Der einzige zu ladende RSS-Artikel betraf Anthropic, nicht die Teaser-Kombination,
und wurde wegen Paywall-Metadaten korrekt abgelehnt. Ergebnis: null Dokumente,
null Primärbelege und null Gegenkandidaten. Ein zusätzliches Publikationsdatum oder
mehr Requests würden diese konkreten Quellenprobleme nicht beheben.

Separater reproduzierter Parserfehler: Die gierige Präfix-Regel für Werberenditen
konsumierte die ersten Stellen von `421` und erfasste nur `1`. Die Präfixsuche wurde
minimal auf nicht-gierig korrigiert und mit einem Regressionstest abgesichert.
Diese Werbezahl ist kein fundamentaler Aktienbeleg; ihre Korrektur erzeugt keinen
SLB-Kandidaten und keine bestätigte Derivatebewertung.

Der alte Lauf wird nicht verändert. Der [extrahierte Diagnosebericht](teaser198-hetzner-diagnosis.json)
enthält dessen SHA-256 und die belegten Befunde. Es wurde kein neues Remote-Deployment
vorgenommen. Für die autonome Recherche bleibt eine tatsächlich verfügbare zulässige
breite Suchquelle erforderlich; die bisherige manuelle SLB-Identifikation wird nicht
als automatisch wiederholter Erfolg ausgegeben.

Ein weiterer Modellengpass ist im Bericht erkennbar: Als Aktienhinweis wurde nur das
generische KI-Merkmal extrahiert. Fördergeschäft, Kühltechnik und wiederkehrende
Digitalerlöse stehen zwar teilweise in Suchfragen, aber nicht als spezifische vergleichbare
Fakten in der Evidenzmatrix. Eine funktionierende Such-API allein ist daher noch kein
Nachweis einer vollständigen Reparatur. Diese Kombination muss künftig quellenbelegt
und unter sauberer Firmenzuordnung geprüft werden; die Identifikationsschranken einfach
abzusenken wäre keine zulässige Lösung.
