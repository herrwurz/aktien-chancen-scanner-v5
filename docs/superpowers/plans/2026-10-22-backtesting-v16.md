# V1.6 implementation design

Use the current main including PR11; retain legacy V1.2 behavior for old Rules.
Add an opt-in V1.6 rule schema and engine, never activate unreviewed proposals.

- Four complete rule types: partial sale, remaining stop, target2 sale, conditional loss exit.
- A loss condition is observed only at a completed close; execute at next session open.
- Session age includes entry as session1; calendar age is local calendar-date difference (entry day0).
- Explicit loss basis: total position including realized partial proceeds, or remaining position.
- Intrabar collisions: conservative stop-first lower bound; ambiguous and not fully evaluable.
- Report event time intervals, target/stop events, initial reward/risk and drawdown of observed modeled equity. True intraday maximum is unknown.
- Independently validated identity, data, availability mode and manually approved source-bound rules gate simulation.
- Add read-only OpenFIGI export/raw/linked-export integrity audit; no forced lookup.
- Reuse V1.5 EODHD authorization/cache boundary; add sanitized append-only usage/error journal.
- Fixed 118-row regression with96 unique WKN/94 synthetic hits and no fabricated real coverage.
- Four reproducible JSON/CSV artifacts plus external SHA-256 sidecar; all source datasets read-only.
- Validate local tests/Ruff and full PostgreSQL/Docker CI, publish new PR, no merge/deployment.
