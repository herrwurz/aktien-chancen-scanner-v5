import csv
import json

import pytest
from test_backtest_report import AS_OF, add_recommendation

from scanner.hebeltrader.historical_pipeline import build_pipeline_report, write_audit


def test_all_118_no_inputs_are_not_fabricated_as_covered(sessions, tmp_path):
    with sessions.begin() as session:
        for index in range(118):
            add_recommendation(session, index)
    with sessions() as session:
        report = build_pipeline_report(session, run_at=AS_OF, as_of=AS_OF)
        assert not session.dirty and not session.new and not session.deleted
    assert report["count"] == 118
    assert report["pipeline_summary"]["historical_identities_verified"] == 0
    assert report["pipeline_summary"]["imported_series"] == 0
    assert report["pipeline_summary"]["research_backtest_ready"] == 0
    assert report["pipeline_summary"]["verified_backtest_ready"] == 0
    assert all(not r["training_eligible"] for r in report["results"])
    a = write_audit(tmp_path / "a", report)
    b = write_audit(tmp_path / "b", report)
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]
    with a[1].open() as stream:
        assert [json.loads(r["record_json"]) for r in csv.DictReader(stream)] == report["results"]


def test_stock_derivative_collision_is_a_blocker_without_modifying_original(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        rec.stock_wkn = rec.derivative_wkn = "SJ6B4A"
    with sessions() as session:
        report = build_pipeline_report(session, run_at=AS_OF, as_of=AS_OF, expected_count=1)
    row = report["results"][0]
    assert "stock_derivative_identifier_collision" in row["identity"]["issues"]
    assert report["identity_audit"]["classification_conflicts"] == 1


def test_cli_sets_sqlite_query_only_and_exports_exclusively(sessions, tmp_path, monkeypatch):
    import pytest
    from sqlalchemy import event

    from scanner.hebeltrader.historical_cli import main

    with sessions.begin() as session:
        add_recommendation(session)
    engine = sessions.kw["bind"]
    statements = []
    event.listen(
        engine, "before_cursor_execute", lambda c, u, s, p, x, m: statements.append(s.upper())
    )
    monkeypatch.setattr("scanner.hebeltrader.historical_cli.create_db", lambda _: engine)
    prefix = tmp_path / "cli"
    assert (
        main(
            [
                "audit",
                "--as-of",
                AS_OF.isoformat(),
                "--run-at",
                AS_OF.isoformat(),
                "--expected-count",
                "1",
                "--output-prefix",
                str(prefix),
            ]
        )
        == 0
    )
    assert "PRAGMA QUERY_ONLY=ON" in statements
    assert all(s.startswith(("SELECT", "PRAGMA QUERY_ONLY=ON")) for s in statements)
    assert (
        main(
            [
                "audit",
                "--as-of",
                AS_OF.isoformat(),
                "--run-at",
                AS_OF.isoformat(),
                "--expected-count",
                "1",
                "--output-prefix",
                str(prefix),
            ]
        )
        == 2
    )
    report = json.loads((tmp_path / "cli.json").read_text())
    with pytest.raises(FileExistsError):
        write_audit(prefix, report)


@pytest.mark.parametrize("mode", ["research", "verified"])
def test_reviewed_synthetic_stock_series_can_be_research_ready_without_verified_release(
    sessions, tmp_path, monkeypatch, mode
):
    from datetime import UTC, date, datetime

    from test_eodhd_adapter import CLOCK, inputs
    from test_historical_identity import source

    from scanner.hebeltrader.eodhd_adapter import prepare_snapshot

    records, calendar, spec = inputs(tmp_path, monkeypatch)
    spec.update(
        coverage_start="2024-12-31T23:00:00+00:00",
        identity_valid_from="2024-12-31T23:00:00+00:00",
        identity_status="verified",
        identity_reviewed_by="Synthetic reviewer",
        identity_reviewed_at=CLOCK.isoformat(),
        identity_reference="https://issuer.example/synthetic-dated-evidence",
        identity_evidence="Synthetic historical identifier proof",
    )
    fields = (
        "wkn",
        "isin",
        "symbol",
        "venue",
        "timezone",
        "currency",
        "identity_valid_from",
        "identity_valid_until",
    )
    evidence = source(dict({k: spec[k] for k in fields}, asset_class="stock"))
    bundle = prepare_snapshot(
        tmp_path / "raw-cache",
        tmp_path / "data",
        records=records,
        spec=spec,
        calendar_path=calendar,
        run_at=CLOCK,
    )
    reviewed = dict(
        bundle["spec"],
        asset_class="stock",
        review_evidence={
            k: dict(payload_sha256=evidence["payload_sha256"], pointer="/" + k)
            for k in (*fields, "asset_class")
        },
    )
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        doc.publication_date = date(2025, 1, 1)
        header = "01.01.2025 #1/2025"
        doc.pages = [dict(number=1, text=doc.pages[0]["text"] + "\n" + header)]
        doc.metadata_evidence = [dict(page=1, raw=header)]
        rec.stock_currency = "USD"
        rec.stock_price = 10
        rec.evidence = dict(rec.evidence, stock_currency=[dict(page=1, raw="USD")])
        rules = {
            f"{doc.sha256}:1": dict(
                document_sha=doc.sha256,
                ordinal=1,
                reviewer="Synthetic reviewer",
                reviewed_at=CLOCK.isoformat(),
                partial_fraction=0.5,
                after_target1="entry",
                evidence=[
                    dict(
                        page=1,
                        quote="Sell 50% at target 1; move stop to entry.",
                        fields=["partial_fraction", "after_target1"],
                    )
                ],
            )
        }
    with sessions() as session:
        report = build_pipeline_report(
            session,
            run_at=CLOCK,
            as_of=datetime(2025, 1, 3, tzinfo=UTC),
            records=[evidence],
            mapping={"AB1234": reviewed},
            rules=rules,
            bundles=[bundle],
            market_root=tmp_path / "data",
            raw_cache=tmp_path / "raw-cache",
            expected_count=1,
            analysis_mode=mode,
        )
    assert report["pipeline_summary"]["historical_identities_verified"] == 1
    assert report["pipeline_summary"]["imported_series"] == 1
    assert report["pipeline_summary"]["research_backtest_ready"] == 1, report["results"][0][
        "blockers"
    ]
    assert report["pipeline_summary"]["verified_backtest_ready"] == 0
    assert report["pipeline_summary"]["warrant_backtest_ready"] == 0


def test_credential_bearing_mapping_is_rejected_before_any_export(sessions):
    import pytest

    with sessions() as session:
        with pytest.raises(ValueError):
            build_pipeline_report(
                session,
                run_at=AS_OF,
                as_of=AS_OF,
                mapping={
                    "AB1234": dict(
                        wkn="AB1234",
                        source_reference="https://example.org/data?api_token=private-token-value",
                    )
                },
            )
