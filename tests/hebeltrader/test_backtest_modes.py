from datetime import UTC, date, datetime

import pytest
from backtest_sample import AS_OF, RUN_AT, market_inputs, rule_inputs, seed_sample
from sqlalchemy import select

from scanner.hebeltrader.backtest_provider import CsvStockProvider
from scanner.hebeltrader.backtest_report import build_report
from scanner.hebeltrader.models import Document


def prepare(sessions, root, published=date(2026, 1, 2), available=None):
    with sessions.begin() as session:
        doc, rec = seed_sample(session)
        doc.publication_date = published
        header = f"{published:%d.%m.%Y} #1/2026"
        doc.pages = [dict(number=1, text=doc.pages[0]["text"] + "\n" + header)]
        doc.metadata_evidence = [dict(page=1, raw=header, rule="header-v1")]
        doc.verified_available_at = available
        doc.availability_evidence = "synthetic release proof" if available else None
        rules = rule_inputs(doc, rec)
    return market_inputs(root), rules


def run(sessions, root, mapping, rules, mode="research", as_of=AS_OF):
    with sessions() as session:
        return build_report(
            session,
            CsvStockProvider(root),
            mapping,
            rules,
            as_of=as_of,
            run_at=RUN_AT,
            analysis_mode=mode,
        )


def test_research_uses_monday_after_friday_without_claiming_availability(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    # A neutral Monday entry allows a path through the Tuesday gap.
    bars = tmp_path / "bars.csv"
    bars.write_text(bars.read_text().replace(",12,13,11,12,200", ",10,11,9,10,200"))
    report = run(sessions, tmp_path, mapping, rules)
    row = report["results"][0]
    assert row["available_at"] is None
    assert row["availability_status"] == "assumed_from_publication_date"
    assert row["analysis_mode"] == report["analysis_mode"] == "research"
    assert row["hypothetical"] and not row["source_verified"] and not row["training_eligible"]
    assert row["observation_window"]["start"] == "2026-01-05T09:30:00+01:00"
    assert row["modeled_entry_at"] == row["observation_window"]["start"]
    assert row["publication_evidence"]["page"] == 1
    assert row["result"]["realized_return_pct"] is None
    with sessions() as session:
        assert session.scalar(select(Document)).verified_available_at is None


@pytest.mark.parametrize("published", [date(2026, 1, 3), date(2026, 1, 4)])
def test_weekend_publication_uses_calendar_monday(sessions, tmp_path, published):
    mapping, rules = prepare(sessions, tmp_path, published)
    report = run(sessions, tmp_path, mapping, rules)
    assert report["results"][0]["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"


def test_calendar_holiday_skips_monday_but_not_a_missing_bar(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    for name in ("bars.csv", "calendar.csv"):
        path = tmp_path / name
        path.write_text(
            "\n".join(
                line for line in path.read_text().splitlines() if not line.startswith("2026-01-05")
            )
            + "\n"
        )
    report = run(sessions, tmp_path, mapping, rules)
    assert report["results"][0]["modeled_entry_at"] == "2026-01-06T09:30:00+01:00"
    # Calendar says Monday trades, but its price is absent: never move entry to Tuesday.
    cal = tmp_path / "calendar.csv"
    cal.write_text(cal.read_text() + "2026-01-05T09:30:00+01:00,2026-01-05T17:30:00+01:00\n")
    report = run(sessions, tmp_path, mapping, rules)
    assert report["results"][0]["result"]["status"] == "unknown"
    assert "missing_sessions" in report["results"][0]["data_issues"]


def test_verified_default_stays_strict(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    with sessions() as session:
        report = build_report(
            session, CsvStockProvider(tmp_path), mapping, rules, as_of=AS_OF, run_at=RUN_AT
        )
    assert report["analysis_mode"] == "verified"
    assert report["results"][0]["result"]["reason"] == "unverified_availability"
    assert report["results"][0]["modeled_entry_at"] is None


def test_intraday_publication_never_uses_same_day_open_in_research(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path, available=datetime(2026, 1, 2, 7, tzinfo=UTC))
    research = run(sessions, tmp_path, mapping, rules)
    verified = run(sessions, tmp_path, mapping, rules, "verified")
    assert research["results"][0]["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"
    assert verified["results"][0]["modeled_entry_at"] == "2026-01-02T09:30:00+01:00"


def test_known_late_release_is_not_bypassed_by_research(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path, available=datetime(2026, 1, 5, 12, tzinfo=UTC))
    report = run(sessions, tmp_path, mapping, rules)
    assert report["results"][0]["modeled_entry_at"] == "2026-01-06T09:30:00+01:00"


def test_incomplete_first_session_is_not_used_or_replaced_by_a_future_bar(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    report = run(sessions, tmp_path, mapping, rules, as_of=datetime(2026, 1, 5, 12, tzinfo=UTC))
    row = report["results"][0]
    assert row["modeled_entry_at"] is None
    assert row["result"]["status"] == "unknown"
    assert "data_unavailable" in row["data_issues"]


def test_research_requires_source_backed_date(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    with sessions.begin() as session:
        session.scalar(select(Document)).metadata_evidence = []
    report = run(sessions, tmp_path, mapping, rules)
    assert report["results"][0]["result"]["reason"] == "unverified_publication_date"


def test_intraday_verified_release_skips_the_already_open_session(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path, available=datetime(2026, 1, 2, 12, tzinfo=UTC))
    for mode in ("verified", "research"):
        report = run(sessions, tmp_path, mapping, rules, mode)
        assert report["results"][0]["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"


def test_research_excludes_publication_date_in_exchange_timezone(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    # Jan 2 23:30 UTC is already Jan 3 in Berlin but is still the exchange's publication day.
    mapping["AB1234"]["timezone"] = "UTC"
    (tmp_path / "bars.csv").write_text(
        "timestamp,end_timestamp,open,high,low,close,volume\n"
        "2026-01-02T23:30:00+00:00,2026-01-02T23:45:00+00:00,10,11,9,10,100\n"
        "2026-01-05T00:00:00+00:00,2026-01-05T08:00:00+00:00,10,11,9,10,100\n"
    )
    (tmp_path / "calendar.csv").write_text(
        "timestamp,end_timestamp\n"
        "2026-01-02T23:30:00+00:00,2026-01-02T23:45:00+00:00\n"
        "2026-01-05T00:00:00+00:00,2026-01-05T08:00:00+00:00\n"
    )
    row = run(sessions, tmp_path, mapping, rules)["results"][0]
    assert row["modeled_entry_at"] == "2026-01-05T00:00:00+00:00"
    assert row["calendar_timezone"] == "UTC"


def test_mode_is_part_of_audit_and_input_hash(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path, available=datetime(2026, 1, 2, 7, tzinfo=UTC))
    verified = run(sessions, tmp_path, mapping, rules, "verified")
    research = run(sessions, tmp_path, mapping, rules)
    assert verified["results"][0]["input_sha256"] != research["results"][0]["input_sha256"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing_date", "missing_publication_date"),
        ("rejected", "excluded_review_status"),
        ("revision", "unresolved_revision_conflict"),
        ("future_release", "not_available_as_of"),
    ],
)
def test_research_does_not_bypass_other_guards(sessions, tmp_path, change, reason):
    mapping, rules = prepare(sessions, tmp_path)
    with sessions.begin() as session:
        doc = session.scalar(select(Document))
        if change == "missing_date":
            doc.publication_date = None
        elif change == "rejected":
            doc.review_status = "rejected"
        elif change == "revision":
            doc.revision_conflict = True
        else:
            doc.verified_available_at = datetime(2027, 1, 1, tzinfo=UTC)
            doc.availability_evidence = "synthetic future release proof"
    row = run(sessions, tmp_path, mapping, rules)["results"][0]
    assert row["result"]["reason"] == reason
    assert row["modeled_entry_at"] is None


@pytest.mark.parametrize("extension", ["json", "csv"])
def test_cli_selects_and_exports_research_audit(tmp_path, monkeypatch, extension):
    import csv
    import json

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from scanner.hebeltrader.cli import main

    url = f"sqlite:///{tmp_path}/modes.db"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    mapping, rules = prepare(sessions, tmp_path)
    for name, data in (("mapping", mapping), ("rules", rules)):
        (tmp_path / f"{name}.json").write_text(json.dumps(data))
    output = tmp_path / f"research.{extension}"
    assert (
        main(
            [
                "backtest",
                "--analysis-mode",
                "research",
                "--bars-dir",
                str(tmp_path),
                "--map",
                str(tmp_path / "mapping.json"),
                "--rules",
                str(tmp_path / "rules.json"),
                "--as-of",
                AS_OF.isoformat(),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    if extension == "json":
        payload = json.loads(output.read_text())
        row = payload["results"][0]
        assert payload["analysis_mode"] == "research"
        assert row["training_eligible"] is False and row["available_at"] is None
    else:
        with output.open() as stream:
            row = next(csv.DictReader(stream))
        assert row["training_eligible"] == "False" and row["available_at"] == ""
        assert row["hypothetical"] == "True"
        assert json.loads(row["audit"])["analysis_mode"] == "research"
    assert row["analysis_mode"] == "research"
    assert row["availability_status"] == "assumed_from_publication_date"
    assert row["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"
    with sessions() as session:
        doc = session.scalar(select(Document))
        assert doc.verified_available_at is None and doc.review_status == "pending"
    engine.dispose()


def test_future_bar_prices_cannot_change_research_result(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    bars = tmp_path / "bars.csv"
    bars.write_text(bars.read_text().replace(",12,13,11,12,200", ",10,11,9,10,200"))
    cutoff = datetime(2026, 1, 5, 18, tzinfo=UTC)
    first = run(sessions, tmp_path, mapping, rules, as_of=cutoff)
    bars.write_text(bars.read_text().replace(",9,11,8,10,300", ",NaN,NaN,NaN,NaN,broken"))
    second = run(sessions, tmp_path, mapping, rules, as_of=cutoff)
    assert first["results"][0]["result"] == second["results"][0]["result"]
    assert first["results"][0]["result"]["status"] == "not_triggered"


def test_overnight_session_already_open_on_publication_day_is_skipped(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    (tmp_path / "bars.csv").write_text(
        (tmp_path / "bars.csv").read_text()
        + "2026-01-02T20:00:00+01:00,2026-01-05T08:00:00+01:00,10,11,9,10,100\n"
    )
    (tmp_path / "calendar.csv").write_text(
        (tmp_path / "calendar.csv").read_text()
        + "2026-01-02T20:00:00+01:00,2026-01-05T08:00:00+01:00\n"
    )
    row = run(sessions, tmp_path, mapping, rules)["results"][0]
    assert row["modeled_entry_at"] == "2026-01-05T09:30:00+01:00"


def test_dst_weekend_uses_exchange_offsets(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path, published=date(2026, 3, 27))
    for key in ("retrieved_at", "coverage_end", "identity_valid_until"):
        mapping["AB1234"][key] = "2026-04-01T00:00:00+02:00"
    (tmp_path / "bars.csv").write_text(
        "timestamp,end_timestamp,open,high,low,close,volume\n"
        "2026-03-30T09:30:00+02:00,2026-03-30T17:30:00+02:00,10,11,9,10,100\n"
    )
    (tmp_path / "calendar.csv").write_text(
        "timestamp,end_timestamp\n2026-03-30T09:30:00+02:00,2026-03-30T17:30:00+02:00\n"
    )
    with sessions() as session:
        report = build_report(
            session,
            CsvStockProvider(tmp_path),
            mapping,
            rules,
            as_of=datetime(2026, 3, 30, 20, tzinfo=UTC),
            run_at=datetime(2026, 4, 2, tzinfo=UTC),
            analysis_mode="research",
        )
    row = report["results"][0]
    assert row["modeled_entry_at"] == "2026-03-30T09:30:00+02:00"
    assert row["entry_cutoff_exclusive"].endswith("+01:00")


def test_118_research_rows_advance_past_availability_without_inventing_rules(sessions):
    from test_backtest_report import NoData, add_recommendation

    with sessions.begin() as session:
        for index in range(118):
            doc, _ = add_recommendation(session, index)
            header = "01.01.2026 #1/2026"
            doc.pages = [dict(number=1, text=header)]
            doc.metadata_evidence = [dict(page=1, raw=header, rule="header-v1")]
    with sessions() as session:
        report = build_report(
            session, NoData(), {}, {}, as_of=AS_OF, run_at=RUN_AT, analysis_mode="research"
        )
    assert report["count"] == 118
    assert report["missing_data"]["reasons"] == {"missing_documented_rules": 118}
    assert all(r["available_at"] is None and not r["training_eligible"] for r in report["results"])


def test_future_calendar_row_cannot_invalidate_historical_research(sessions, tmp_path):
    mapping, rules = prepare(sessions, tmp_path)
    bars = tmp_path / "bars.csv"
    bars.write_text(bars.read_text().replace(",12,13,11,12,200", ",10,11,9,10,200"))
    cutoff = datetime(2026, 1, 5, 18, tzinfo=UTC)
    before = run(sessions, tmp_path, mapping, rules, as_of=cutoff)
    cal = tmp_path / "calendar.csv"
    cal.write_text(cal.read_text() + "2026-01-10T09:30:00+01:00,invalid-future-close\n")
    after = run(sessions, tmp_path, mapping, rules, as_of=cutoff)
    assert before["results"][0]["result"] == after["results"][0]["result"]
