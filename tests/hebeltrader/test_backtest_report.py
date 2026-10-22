import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from scanner.hebeltrader import backtest_report
from scanner.hebeltrader.models import Document, HistoricalOutcome, HistoricalRecommendation

AS_OF = datetime(2026, 2, 1, tzinfo=UTC)


def add_recommendation(session, index=0):
    data = f"synthetic PDF {index}".encode()
    sha = hashlib.sha256(data).hexdigest()
    doc = Document(
        sha256=sha,
        publication_date=date(2026, 1, 1),
        original_pdf=data,
        byte_size=len(data),
        extractor_version="synthetic",
        imported_at=AS_OF,
        extraction_status="extracted",
        review_status="pending",
        revision_conflict=False,
        pages=[{"number": 1, "text": "Sell 50% at target 1; move stop to entry."}],
        flags=[],
        metadata_evidence=[],
    )
    rec = HistoricalRecommendation(
        document_sha=sha,
        ordinal=1,
        stock_wkn="AB1234",
        stock_currency="EUR",
        stock_target1=12,
        stock_target2=15,
        stock_stop1=8,
        stock_stop2=9,
        evidence={
            k: [{"page": 1, "raw": str(v)}]
            for k, v in {"stock_target1": 12, "stock_target2": 15, "stock_stop1": 8}.items()
        },
        flags=[],
    )
    session.add_all([doc, rec])
    session.flush()
    return doc, rec


class NoData:
    def load(self, *args, **kwargs):
        raise AssertionError("Unverified availability must not load market history")


def test_prepares_all_118_without_labels_or_writes(sessions):
    with sessions.begin() as s:
        for index in range(118):
            add_recommendation(s, index)
    with sessions() as s:
        report = backtest_report.build_report(s, NoData(), {}, {}, as_of=AS_OF, run_at=AS_OF)
        assert report["count"] == 118
        assert report["counts"] == {"unknown": 118}
        assert report["coverage"]["source_verified"] == 0
        assert report["success_rate"] is None
        assert all(r["result"]["reason"] == "unverified_availability" for r in report["results"])
        assert all(r["derivative"]["status"] == "derivative_unverified" for r in report["results"])
        assert all(not r["training_eligible"] for r in report["results"])
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(HistoricalOutcome)) == 0
        assert s.scalar(select(func.count()).select_from(HistoricalRecommendation)) == 118
        assert set(s.scalars(select(Document.review_status))) == {"pending"}


def test_document_rules_need_exact_source_quote(sessions):
    with sessions.begin() as s:
        doc, rec = add_recommendation(s)
        spec = dict(
            document_sha=doc.sha256,
            ordinal=1,
            partial_fraction="0.5",
            after_target1="entry",
            reviewer="tester",
            reviewed_at=AS_OF.isoformat(),
            evidence=[
                dict(
                    page=1,
                    quote="Sell 50% at target 1; move stop to entry.",
                    fields=["partial_fraction", "after_target1"],
                )
            ],
        )
        rule, audit, issue = backtest_report.document_rules(doc, rec, spec, AS_OF)
        assert issue is None and rule.after_target1 == "entry"
        assert audit["document_sha"] == doc.sha256
        spec["evidence"][0]["quote"] = "invented source"
        assert (
            backtest_report.document_rules(doc, rec, spec, AS_OF)[2] == "unverified_rule_evidence"
        )


def test_future_availability_and_rejected_source_never_simulate(sessions):
    with sessions.begin() as s:
        doc, rec = add_recommendation(s)
        doc.verified_available_at = datetime(2027, 1, 1, tzinfo=UTC)
        doc.availability_evidence = "archive proof"
    with sessions() as s:
        report = backtest_report.build_report(s, NoData(), {}, {}, as_of=AS_OF, run_at=AS_OF)
        assert report["results"][0]["result"]["reason"] == "not_available_as_of"
    with sessions.begin() as s:
        s.scalar(select(Document)).review_status = "rejected"
    with sessions() as s:
        report = backtest_report.build_report(s, NoData(), {}, {}, as_of=AS_OF, run_at=AS_OF)
        assert report["results"][0]["result"]["reason"] == "excluded_review_status"


def test_cli_json_csv_are_exclusive_and_private(tmp_path, monkeypatch):
    import json

    from alembic import command
    from alembic.config import Config

    from scanner.hebeltrader.backtest_cli import main

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/backtest.db")
    command.upgrade(Config("alembic.ini"), "head")
    mapping = tmp_path / "mapping.json"
    mapping.write_text("{}")
    args = ["--bars-dir", str(tmp_path), "--map", str(mapping), "--as-of", AS_OF.isoformat()]
    target = tmp_path / "empty.json"
    assert main([*args, "--output", str(target)]) == 0
    report = json.loads(target.read_text())
    assert report["count"] == 0 and report["success_rate"] is None
    assert target.stat().st_mode & 0o777 == 0o600
    assert main([*args, "--output", str(target)]) == 2
    assert json.loads(target.read_text()) == report
    csv = tmp_path / "empty.csv"
    assert main([*args, "--output", str(csv)]) == 0
    assert csv.read_text().startswith("recommendation_id,")
    assert csv.stat().st_mode & 0o777 == 0o600
    assert b"\r" not in csv.read_bytes()


def test_real_provider_rule_evidence_and_partial_exit_end_to_end(sessions, tmp_path):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, rule_inputs, seed_sample

    from scanner.hebeltrader.backtest_provider import CsvStockProvider

    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        rules = rule_inputs(doc, rec)
    with sessions() as s:
        payload = backtest_report.build_report(
            s,
            CsvStockProvider(tmp_path),
            market_inputs(tmp_path),
            rules,
            as_of=AS_OF,
            run_at=RUN_AT,
        )
        row = payload["results"][0]
        assert row["result"]["status"] == "target1_first"
        assert row["result"]["exit_reason"] == "target1_then_stop"
        assert row["result"]["modeled_return_pct"] == "5.0"
        assert row["result"]["realized_return_pct"] is None
        assert [e["at_price"] for e in row["result"]["events"]] == ["12", "9"]
        assert row["derivative"]["term_text"] == "open end"
        assert row["derivative"]["status"] == "derivative_unverified"
        assert row["source"]["sha256"]["file"]
        assert payload["coverage"]["market_data_complete"] == 1
        assert not row["training_eligible"] and not row["source_verified"]


def test_subcommand_dispatch_and_errors(tmp_path, monkeypatch):
    from scanner.hebeltrader.cli import main

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/unused.db")
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert (
        main(
            [
                "backtest",
                "--bars-dir",
                str(tmp_path),
                "--map",
                str(bad),
                "--as-of",
                AS_OF.isoformat(),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "out.json").exists()


def test_invalid_or_uncovered_time_rule_is_unknown(sessions):
    from backtest_sample import RUN_AT, rule_inputs, seed_sample

    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        spec = next(iter(rule_inputs(doc, rec).values()))
        spec["exit_after"] = {"days": 20, "unit": "trading_sessions"}
        assert (
            backtest_report.document_rules(doc, rec, spec, RUN_AT)[2] == "unverified_rule_evidence"
        )
        spec["exit_after"] = {"days": -1, "unit": "invented"}
        assert (
            backtest_report.document_rules(doc, rec, spec, RUN_AT)[2] == "unverified_rule_evidence"
        )


def test_missing_market_files_are_categorized_not_a_batch_error(sessions, tmp_path):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, rule_inputs, seed_sample

    from scanner.hebeltrader.backtest_provider import CsvStockProvider

    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        rules = rule_inputs(doc, rec)
    mapping = market_inputs(tmp_path)
    (tmp_path / "bars.csv").unlink()
    with sessions() as s:
        report = backtest_report.build_report(
            s, CsvStockProvider(tmp_path), mapping, rules, as_of=AS_OF, run_at=RUN_AT
        )
    assert report["results"][0]["result"]["status"] == "unknown"
    assert report["missing_data"]["issues"]["data_unavailable"] == 1


def test_cli_full_synthetic_case_keeps_database_unchanged(tmp_path, monkeypatch):
    import csv
    import json

    from alembic import command
    from alembic.config import Config
    from backtest_sample import AS_OF, market_inputs, rule_inputs, seed_sample
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from scanner.hebeltrader.cli import main

    url = f"sqlite:///{tmp_path}/sample.db"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        rules = rule_inputs(doc, rec)
    mapping = market_inputs(tmp_path)
    map_file, rules_file = tmp_path / "mapping.json", tmp_path / "rules.json"
    map_file.write_text(json.dumps(mapping))
    rules_file.write_text(json.dumps(rules))
    args = [
        "backtest",
        "--bars-dir",
        str(tmp_path),
        "--map",
        str(map_file),
        "--rules",
        str(rules_file),
        "--as-of",
        AS_OF.isoformat(),
    ]
    for extension in ("json", "csv"):
        target = tmp_path / f"result.{extension}"
        assert main([*args, "--output", str(target)]) == 0
    report = json.loads((tmp_path / "result.json").read_text())
    with (tmp_path / "result.csv").open() as f:
        row = list(csv.DictReader(f))[0]
    assert row["status"] == report["results"][0]["result"]["status"] == "target1_first"
    assert row["realized_return_pct"] == ""
    assert json.loads(row["audit"])["success_rate"] is None
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(HistoricalOutcome)) == 0
        assert s.scalar(select(Document)).review_status == "pending"
        assert s.scalar(select(HistoricalRecommendation)).stock_price == 10
    engine.dispose()


def test_selected_approved_revision_with_availability_is_resolved(sessions):
    from scanner.hebeltrader.models import Publication

    with sessions.begin() as s:
        doc, rec = add_recommendation(s)
        issue = Publication(issue_year=2026, issue_number=1, selected_sha=doc.sha256)
        s.add(issue)
        s.flush()
        doc.publication_id = issue.id
        doc.review_status = "approved"
        doc.revision_conflict = True
        doc.verified_available_at = datetime(2026, 1, 2, tzinfo=UTC)
        doc.availability_evidence = "source-specific release proof"
    with sessions() as s:
        report = backtest_report.build_report(s, NoData(), {}, {}, as_of=AS_OF, run_at=AS_OF)
    assert report["results"][0]["source_verified"] is True
    assert report["results"][0]["result"]["reason"] == "missing_documented_rules"


def test_malformed_source_metadata_does_not_abort_batch(sessions, tmp_path):
    from backtest_sample import AS_OF, RUN_AT, market_inputs, rule_inputs, seed_sample

    from scanner.hebeltrader.backtest_provider import CsvStockProvider

    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        rules = rule_inputs(doc, rec)
    mapping = market_inputs(tmp_path)
    mapping["AB1234"]["retrieved_at"] = "not a timestamp"
    with sessions() as s:
        report = backtest_report.build_report(
            s, CsvStockProvider(tmp_path), mapping, rules, as_of=AS_OF, run_at=RUN_AT
        )
    assert report["results"][0]["result"]["status"] == "unknown"
    assert "missing_metadata" in report["results"][0]["data_issues"]


def test_malformed_reviewer_does_not_abort_rule_check(sessions):
    from backtest_sample import RUN_AT, rule_inputs, seed_sample

    with sessions.begin() as s:
        doc, rec = seed_sample(s)
        spec = next(iter(rule_inputs(doc, rec).values()))
        for value in (None, 17, [], {}):
            spec["reviewer"] = value
            assert (
                backtest_report.document_rules(doc, rec, spec, RUN_AT)[2]
                == "unverified_rule_evidence"
            )
