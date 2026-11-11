# HEBELTRADER 199/26 – Nasdaq: historischer Pilot-Audit

**Prüfstand:** 11.11.2026 · **Status:** `original_register_only / execution_unverified / call_performance_not_evaluable` · Keine nachgewiesene Handelsrendite.

## 1. Quellen- und Integritätskette

- Maßgeblicher Registereintrag: [hebeltrader-identification-rules.md](hebeltrader-identification-rules.md), Abschnitt „Original-PDF 199/26“ und Originalcall-Sammlung.
- Strukturierter Registerauszug: [hebeltrader-originalreports-42.json](hebeltrader-originalreports-42.json), Schlüssel `199/26`.
- Genannter Originaldateiname: `Hebeltrader_2026-199.pdf`.
- Übernommener Original-PDF-SHA-256: `3817b74c93f9db92420fe9013e2ea0c0f93c711e50b747d66c01df11c6dc58e0`.
- Original-PDF wurde in dieser Prüfung **nicht neu geöffnet oder byteweise mit dem Hash abgeglichen**. Alle folgenden Marken sind **Register-Abschriften mit genannten PDF-Seiten**, keine unabhängige Neuverifikation.

## 2. Originalmarken / Verlagsszenarien (keine realisierten Gewinne)

| Feld | Aktie | Call |
|---|---|---|
| Instrument | Nasdaq Inc. / WKN 813516 | JY7FDN |
| Ausgabe / Datum | 199/26, 27.10.2026 | 199/26, 27.10.2026 |
| Referenzindikation | 104,72 USD | 0,22 EUR um 08:15 laut Register |
| Empfohlener Einstieg | Nicht ausgewiesen | 0,220 EUR (S. 2) |
| Ausdrücklich separates Kauflimit | Nicht ausgewiesen | Nicht ausgewiesen |
| Ziel 1 | 122 USD | 0,82 EUR |
| Ziel 2 | 153 USD | 3,05 EUR |
| Stopp 1 | 94 USD | 0,08 EUR |
| Stopp 2 | 104,72 USD | 0,22 EUR |
| Basispreis / Laufzeit | entfällt | 120 USD / 19.03.2027 |
| Omega / Volatilität | entfällt | 10,0 / ca. 30 % implizite Volatilität |
| Verlags-Szenario | kein ausgeführter Trade | +273 % / +1.286 %, CRV 12,25 |
| PDF-Seitenbeleg laut Register | S. 3 | S. 1–2 |

Die im Original vorgerechneten Renditen sind **Szenariowerte auf dem empfohlenen Einstieg**; sie belegen weder historische Zielberührung noch einen ausführbaren Geldkurs. Die Aktie wird nicht mit der Derivatelaufzeit automatisch geschlossen.

## 3. Regelprüfung (PDF S. 6 laut Register; als Quellenabschrift)

1. Bei Ziel 1: 50 % verkaufen; Stopp für Rest auf Einstieg anheben.
2. Spätestens 20 **Handelstage** nach Ziel 1: Stopp auf 80 % des Ziel-1-Wertes anheben.
3. Bei Verlust nach **mindestens 20 Handelstagen**: Position schließen. Der Begriff `im Minus`, Bewertung und Ausführungszeitpunkt müssen für den Backtest explizit fixiert werden.
4. Offene Derivate spätestens 20 Handelstage vor Laufzeitende schließen.
5. Kein Einstieg, wenn Aktie weniger als 2 % vom empfohlenen Stopp entfernt; bei bereits erreichtem Ziel 1 vor Einstieg nur halbe Position mit angepasstem Stopp.

**Instrument-Scope:** Diese Aussagen stehen in den Anlagegrundsätzen zu Optionsscheinen; für eine eigenständige Aktienstrategie sind eigene, vom Original gedeckte Geltungsbereichsregeln erforderlich. Ziel-/Stoppwerte der Aktie sind Beobachtungsmarken, nicht automatisch ein Aktienkaufplan.

## 4. Fehlende Belege – Freigabesperren

| Teilprüfung | Status | Benötigt |
|---|---|---|
| PDF/Originalmarken | `transcribed_unverified` | Original-PDF, erneuter SHA- und Seitenabgleich; insbesondere Regeln S. 6 |
| Erscheinungs-/Verfügbarkeitszeit | `unverified` | Quelle mit tatsächlichem Publikationszeitpunkt; „08:15“ ist zunächst Referenzkurszeit |
| Basiswert-Identität | `partially_documented` | Historische ISIN, MIC, Börsenzeitzone, Währung und Corporate Actions |
| Aktienkursereignisse | `not_evaluated` | Geschlossene historische OHLCV-Sitzungen ab verfügbarem Einstieg, Kalender, Splits/Dividenden |
| Derivat-Produktbedingungen | `unverified` | ISIN, Emittent, Bezugsverhältnis, Ausübungs-/Abrechnungsart, letzter Handelstag |
| Tatsächlich handelbare Derivatkurse | `missing` | Zeitgestempelte Geld-/Briefkurse, Stückquotierung und Handelsunterbrechungen |
| Kosten | `missing` | Zeitpassende Gebühren, gegebenenfalls Slippage / FX |
| Reale Trades | `not_supplied` | Ausführungsbelege, Teilverkäufe, Ausstiege und Gebühren |

**Folge:** `verified_stock_return_pct=null`, `verified_call_return_pct=null`, `realized_net_return_pct=null`. Derzeit keine Erfolgsquote oder Gewinn-/Verluststatistik für diesen Pilot ableitbar.

## 5. Vorgesehener historischer Ereignislauf

- Erst Originalseiten gegen Register und Produktbedingungen prüfen; Konflikte als Review dokumentieren, nicht stillschweigend überschreiben.
- Danach tatsächliche öffentliche Verfügbarkeit und erste mögliche Handelssitzung bestimmen, ohne Rückschau auf spätere Kursbewegungen.
- Aktienziele und -stopps anhand verifizierter Tagessitzungen nur als Kursereignisse protokollieren; gleichzeitige intraday Berührung als mehrdeutig markieren.
- Derivatstrategie separat mit zeitlich passenden ausführbaren Bid/Ask-Quoten prüfen; bei fehlender Geldkursreihe Abbruch statt Black-Scholes als „historischen Gewinn“ auszugeben.
- Persönliche Transaktionen ausschließlich mit Orderabrechnungen und vollständigen Gebühren getrennt abrechnen. Offene Restpositionen offen lassen.

## 6. Datensatzdefinition für spätere Ergebnisse

```json
{
  "issue": "199/26",
  "as_of": "2026-11-11",
  "source_class": "register_transcription_not_pdf_reverified",
  "price_event_status": "not_evaluated",
  "derivative_execution_status": "missing_historical_bid_ask",
  "actual_trade_status": "not_supplied",
  "verified_stock_return_pct": null,
  "verified_call_return_pct": null,
  "realized_net_return_pct": null
}
```

Diese Datei dokumentiert einen **abgeschlossenen Datenfreigabe-Audit**, keinen abgeschlossenen historischen Rendite-Backtest. Kein Scanner, keine Weboberfläche, keine Serveranbindung oder Orderausführung.
