from datetime import UTC, datetime

from sqlalchemy import func, select
from test_backtest_report import add_recommendation

from scanner.hebeltrader import coverage
from scanner.hebeltrader.models import HistoricalOutcome, HistoricalRecommendation

AS_OF = datetime(2026, 2, 1, tzinfo=UTC)


def test_all_118_have_independent_blockers_and_repeatable_inventory(sessions):
    with sessions.begin() as session:
        for index in range(118):
            add_recommendation(session, index)
    with sessions() as session:
        first = coverage.build_coverage(session, {}, {}, as_of=AS_OF, run_at=AS_OF)
        second = coverage.build_coverage(session, {}, {}, as_of=AS_OF, run_at=AS_OF)
    assert first == second
    assert first["count"] == 118
    assert len({r["recommendation_key"] for r in first["results"]}) == 118
    assert all(len(r["blockers"]) >= 4 for r in first["results"])
    assert first["summary"]["derivative_bid_ask_verified"]["complete"] == 0
    assert first["success_rate"] is None
    assert all(not r["training_eligible"] for r in first["results"])
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(HistoricalOutcome)) == 0
        assert session.scalar(select(func.count()).select_from(HistoricalRecommendation)) == 118


def test_publication_stage_is_independent_of_missing_rules_and_prices(sessions):
    with sessions.begin() as session:
        doc, _ = add_recommendation(session)
        doc.pages = [dict(number=1, text="01.01.2026 #1/2026")]
        doc.metadata_evidence = [dict(page=1, raw="01.01.2026 #1/2026", rule="header-v1")]
    with sessions() as session:
        report = coverage.build_coverage(
            session, {}, {}, as_of=AS_OF, run_at=AS_OF, expected_count=1
        )
    row = report["results"][0]
    assert row["stages"]["publication_evidenced"]["status"] == "complete"
    assert row["stages"]["rules_documented"]["status"] != "complete"
    assert row["stages"]["market_history_sufficient"]["status"] != "complete"
    assert "unverified_availability" in row["blockers"]
    assert report["warnings"] == []


def test_export_pair_is_consistent_private_and_never_overwrites(tmp_path):
    import csv
    import json

    import pytest

    from scanner.hebeltrader.coverage_cli import write_reports

    report = dict(
        version="test",
        count=1,
        results=[
            dict(
                recommendation_key="source:1",
                document_sha="source",
                ordinal=1,
                publication_date=None,
                values={"stock_wkn": "AB1234", "stock_isin": None},
                stages={},
                blockers=["missing"],
                rule_candidates=[],
                training_eligible=False,
            )
        ],
        manual_review=[],
        summary={},
    )
    prefix = tmp_path / "inventory"
    write_reports(prefix, report)
    payload = json.loads(prefix.with_suffix(".json").read_text())
    with prefix.with_suffix(".csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert json.loads(rows[0]["record_json"]) == payload["results"][0]
    assert prefix.with_suffix(".json").stat().st_mode & 0o777 == 0o600
    assert prefix.with_suffix(".csv").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_reports(prefix, report)
    other = tmp_path / "partial"
    other.with_suffix(".csv").write_text("existing")
    with pytest.raises(FileExistsError):
        write_reports(other, report)
    assert not other.with_suffix(".json").exists()
    assert other.with_suffix(".csv").read_text() == "existing"


def test_market_and_identity_can_be_complete_while_rules_and_availability_missing(
    sessions, tmp_path
):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, seed_sample

    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        rec.evidence = dict(rec.evidence, stock_currency=[dict(page=1, raw="EUR")])
        doc.verified_available_at = None
        doc.availability_evidence = None
    mapping = market_inputs(tmp_path)
    mapping["AB1234"].update(
        identity_status="verified",
        identity_evidence="synthetic historical listing",
        identity_reviewed_by="tester",
        identity_reviewed_at=RUN_AT.isoformat(),
    )
    bars = tmp_path / "bars.csv"
    bars.write_text(bars.read_text().replace(",12,13,11,12,200", ",10,11,9,10,200"))
    with sessions() as session:
        report = coverage.build_coverage(
            session, mapping, {}, bars_dir=tmp_path, as_of=AS_OF, run_at=RUN_AT, expected_count=1
        )
    row = report["results"][0]
    for name in (
        "publication_evidenced",
        "instrument_identity_verified",
        "market_history_sufficient",
        "modeled_entry_executable",
    ):
        assert row["stages"][name]["status"] == "complete", row
    assert row["stages"]["verified_availability"]["status"] == "incomplete"
    assert row["stages"]["rules_documented"]["status"] == "incomplete"
    assert row["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"
    assert row["rule_candidates"][0]["requires_manual_review"] is True
    assert not row["training_eligible"]


def test_bad_dates_do_not_hide_rule_and_identity_proposals(sessions):
    from backtest_sample import QUOTE, RUN_AT, rule_inputs, seed_sample

    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        doc.publication_date = None
        rules = rule_inputs(doc, rec)
    with sessions() as session:
        report = coverage.build_coverage(
            session, {}, rules, as_of=AS_OF, run_at=RUN_AT, expected_count=1
        )
    row = report["results"][0]
    assert row["stages"]["publication_evidenced"]["status"] == "incomplete"
    assert row["stages"]["rules_documented"]["status"] == "complete"
    assert QUOTE in row["rule_candidates"][0]["quote"]


def test_coverage_cli_118_offline_json_csv_consistency(tmp_path, monkeypatch):
    import csv
    import json
    import socket

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from scanner.hebeltrader.cli import main

    url = f"sqlite:///{tmp_path}/coverage.db"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        for index in range(118):
            add_recommendation(session, index)

    def forbidden(*args, **kwargs):
        raise AssertionError("Coverage inventory must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    args = ["coverage", "--as-of", AS_OF.isoformat(), "--run-at", AS_OF.isoformat()]
    for name in ("first", "second"):
        assert main([*args, "--output-prefix", str(tmp_path / name)]) == 0
    first = json.loads((tmp_path / "first.json").read_text())
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
    with (tmp_path / "first.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert [json.loads(row["record_json"]) for row in rows] == first["results"]
    assert first["count"] == 118
    assert main([*args, "--output-prefix", str(tmp_path / "first")]) == 2
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(HistoricalRecommendation)) == 118
    engine.dispose()


def test_missing_levels_are_reported_even_without_identity_or_market(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        rec.stock_target1 = None
        rec.stock_stop1 = None
        rec.stock_wkn = None
    with sessions() as session:
        report = coverage.build_coverage(
            session, {}, {}, as_of=AS_OF, run_at=AS_OF, expected_count=1
        )
    row = report["results"][0]
    assert "missing_stock_identifier" in row["blockers"]
    assert "missing_value:stock_target1" in row["blockers"]
    assert "missing_value:stock_stop1" in row["blockers"]
    assert "missing_documented_rules" in row["blockers"]


def test_unknown_currency_never_becomes_executable_from_mapping(sessions, tmp_path):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, seed_sample

    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        rec.stock_currency = None
    mapping = market_inputs(tmp_path)
    mapping["AB1234"].update(
        identity_status="verified",
        identity_evidence="historical listing proof",
        identity_reviewed_by="tester",
        identity_reviewed_at=RUN_AT.isoformat(),
    )
    with sessions() as session:
        row = coverage.build_coverage(
            session, mapping, {}, bars_dir=tmp_path, as_of=AS_OF, run_at=RUN_AT, expected_count=1
        )["results"][0]
    assert row["stages"]["instrument_identity_verified"]["status"] == "complete"
    assert row["stages"]["market_history_sufficient"]["status"] == "complete"
    assert row["stages"]["modeled_entry_executable"]["status"] == "incomplete"
    assert "missing_price_currency_evidence" in row["blockers"]


def test_confirmed_snapshot_flows_through_identity_to_coverage(sessions, tmp_path):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, seed_sample

    from scanner.hebeltrader.market_snapshot import snapshot_dataset

    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        rec.evidence = dict(rec.evidence, stock_currency=[dict(page=1, raw="EUR")])
    spec = market_inputs(tmp_path)["AB1234"]
    spec.update(
        identity_status="verified",
        identity_evidence="synthetic dated listing",
        identity_reviewed_by="tester",
        identity_reviewed_at=RUN_AT.isoformat(),
    )
    frozen = snapshot_dataset(tmp_path, tmp_path / "snapshots", spec)
    with sessions() as session:
        report = coverage.build_coverage(
            session,
            {"AB1234": frozen},
            {},
            bars_dir=tmp_path,
            as_of=AS_OF,
            run_at=RUN_AT,
            expected_count=1,
        )
    row = report["results"][0]
    assert row["stages"]["market_history_sufficient"]["status"] == "complete"
    assert row["market"]["source"]["snapshot"]["version"] == frozen["snapshot"]["version"]
    assert row["stages"]["instrument_identity_verified"]["status"] == "complete"
    source = tmp_path / frozen["file"]
    source.write_bytes(source.read_bytes() + b"tampered")
    with sessions() as session:
        row = coverage.build_coverage(
            session,
            {"AB1234": frozen},
            {},
            bars_dir=tmp_path,
            as_of=AS_OF,
            run_at=RUN_AT,
            expected_count=1,
        )["results"][0]
    assert "snapshot_hash_mismatch" in row["blockers"]
    assert row["stages"]["market_history_sufficient"]["status"] == "incomplete"
