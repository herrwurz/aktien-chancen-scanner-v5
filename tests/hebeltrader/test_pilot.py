"""All market observations in these fixtures are synthetic, never real JNJ prices."""

from copy import deepcopy


def test_archived_synthetic_history_produces_separate_observations_and_stock_model(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
        assert not session.dirty and not session.new and not session.deleted
    assert report["original_recommendation"]["values"]["stock_wkn"] == "853260"
    assert report["stock_model"]["status"] == "closed"
    assert report["stock_model"]["modeled_entry_at"].startswith("2025-08-06T09:30:00")
    assert report["stock_model"]["modeled_entry"] == "172"
    assert [e["event"] for e in report["stock_model"]["events"]] == ["target1", "target2"]
    assert report["quality"]["classification"] == "research_only"
    assert report["data_classification"] == "synthetic"
    assert report["derivative_observations"]["return_pct"] is None
    assert report["price_events"] and all("ohlcv" in e for e in report["price_events"])
    assert report["historical_market_data"]["missing_sessions"] == []
    assert report["training_eligible"] is False


def test_missing_identity_rules_and_calendar_review_never_invent_an_outcome(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    inputs.update(mapping={}, rules={}, projection_review=None, calendar_review=None)
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert report["quality"]["classification"] == "blocked"
    assert report["stock_model"]["modeled_return_pct"] is None
    assert "historical_identity_unverified" in report["quality"]["blockers"]
    assert "calendar_source_review_required" in report["quality"]["blockers"]
    assert all(e["identity_status"] == "unverified" for e in report["price_events"])


def test_missing_real_record_returns_concrete_blocker_without_using_brief_values(sessions):
    from pilot_fixtures import CLOCK

    from scanner.hebeltrader.pilot import build_pilot_report

    with sessions() as session:
        report = build_pilot_report(session, run_at=CLOCK)
    assert report["original_recommendation"]["loaded"] is False
    assert "original_recommendation_not_found" in report["quality"]["blockers"]
    assert report["price_events"] == []
    assert report["stock_model"]["modeled_return_pct"] is None


def test_missing_session_and_unreviewed_dividends_block_model(sessions, tmp_path, monkeypatch):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    missing = fixture(sessions, tmp_path, monkeypatch, missing=True)
    with sessions() as session:
        report = build_pilot_report(session, **missing)
    assert "missing_sessions" in report["quality"]["blockers"]
    assert report["historical_market_data"]["missing_sessions"] == ["2025-08-07T09:30:00-04:00"]
    assert report["stock_model"]["modeled_return_pct"] is None
    assert report["price_events"] == []


def test_dividend_reconciliation_is_explicit_and_bound_to_original_raw_hashes(
    sessions, tmp_path, monkeypatch
):
    from copy import deepcopy

    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch, dividend=True)
    with sessions() as session:
        approved = build_pilot_report(session, **inputs)
        assert approved["stock_model"]["status"] == "closed"
        assert approved["historical_market_data"]["corporate_actions_reconciled"] is True
        assert (
            "cash dividends excluded" in approved["historical_market_data"]["price_return_policy"]
        )
        inputs["action_review"] = deepcopy(inputs["action_review"])
        inputs["action_review"]["raw_manifests"]["div"] = "0" * 64
        blocked = build_pilot_report(session, **inputs)
    assert "corporate_action_requires_reconciliation" in blocked["quality"]["blockers"]
    assert blocked["stock_model"]["modeled_return_pct"] is None


def test_no_derivative_projection_without_separate_human_scope_decision(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    inputs["projection_review"]["additional_document_rules_reviewed"] = False
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert "explicit_stock_projection_review_required" in report["quality"]["blockers"]
    assert report["price_events"]
    assert report["stock_model"]["events"] == []


def test_unverified_availability_and_ambiguous_days_stay_blocked_in_strict_mode(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    inputs["analysis_mode"] = "verified"
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert "unverified_availability" in report["quality"]["blockers"]
    assert report["stock_model"]["modeled_return_pct"] is None


def test_pilot_artifacts_reproduce_offline_and_hash_detects_changes(
    sessions, tmp_path, monkeypatch
):
    import pytest
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report
    from scanner.hebeltrader.pilot_artifacts import verify_report, write_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    a, b = tmp_path / "a", tmp_path / "b"
    left, right = write_report(a, report), write_report(b, report)
    assert [p.read_bytes() for p in left] == [p.read_bytes() for p in right]
    assert verify_report(a)
    with pytest.raises(FileExistsError):
        write_report(a, report)
    left[1].write_text("modified")
    with pytest.raises(ValueError, match="integrity"):
        verify_report(a)


def test_independent_price_drawdown_is_not_model_return_or_executed_hold_period():
    from test_backtest_v16 import bar

    from scanner.hebeltrader.pilot_market import price_path_metrics

    result = price_path_metrics([bar(0), bar(1, c=99), bar(2, c=98), bar(3, c=101)])
    assert result["close_price_max_drawdown_pct"] == "2"
    assert result["longest_losing_close_episode"]["sessions"] == 2
    assert result["scope"] == "observed_stock_prices; independent of strategy holding period"


def test_cli_is_readonly_and_keeps_blocked_report_reviewable(sessions, tmp_path, monkeypatch):
    import json

    from pilot_fixtures import CLOCK
    from sqlalchemy import event

    from scanner.hebeltrader.pilot_cli import main

    engine = sessions.kw["bind"]
    statements = []
    event.listen(engine, "before_cursor_execute", lambda c, u, s, p, x, m: statements.append(s))
    monkeypatch.setattr("scanner.hebeltrader.pilot_cli.create_db", lambda _: engine)
    prefix = tmp_path / "blocked"
    assert main(["run", "--run-at", CLOCK.isoformat(), "--output-prefix", str(prefix)]) == 2
    assert all(s.upper().startswith(("SELECT", "PRAGMA QUERY_ONLY=ON")) for s in statements)
    report = json.loads((tmp_path / "blocked.json").read_bytes())
    assert report["quality"]["classification"] == "blocked"
    assert main(["verify", "--output-prefix", str(prefix)]) == 0


def test_offline_replay_uses_no_collector_and_same_report(sessions, tmp_path, monkeypatch):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.eodhd import EodhdClient
    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("Pilot must never fetch from an API")

    monkeypatch.setattr(EodhdClient, "fetch", forbidden)
    with sessions() as session:
        assert build_pilot_report(session, **inputs) == build_pilot_report(session, **inputs)


def test_split_is_not_cleared_by_price_only_dividend_approval(sessions, tmp_path, monkeypatch):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch, split=True)
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert "split_price_level_reconciliation_required" in report["quality"]["blockers"]
    assert report["price_events"] == []
    assert report["stock_model"]["modeled_return_pct"] is None


def test_calendar_source_tampering_cannot_be_approved_by_matching_csv_only(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    (tmp_path / "raw" / "calendar-source.txt").write_text("changed source")
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert "calendar_source_review_required" in report["quality"]["blockers"]
    assert report["stock_model"]["modeled_return_pct"] is None


def test_different_original_target_is_preserved_and_reported_not_replaced(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture
    from sqlalchemy import select

    from scanner.hebeltrader.models import HistoricalRecommendation
    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    with sessions.begin() as session:
        session.scalar(select(HistoricalRecommendation)).stock_target1 = 191
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
        assert session.scalar(select(HistoricalRecommendation)).stock_target1 == 191
    assert "original_value_mismatch:stock_target1" in report["quality"]["blockers"]
    assert report["original_recommendation"]["values"]["stock_target1"].startswith("191")
    assert report["stock_model"]["modeled_return_pct"] is None


def test_collision_gap_and_loss_after_twenty_days(sessions, tmp_path, monkeypatch):
    # Separate synthetic inventories; each test database remains unchanged by the report.
    from pilot_fixtures import fixture
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from scanner.hebeltrader.pilot import build_pilot_report
    from scanner.models import Base

    results = {}
    for scenario in ("collision", "gap", "loss20", "profitable"):
        root = tmp_path / scenario
        root.mkdir()
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine)
        inputs = fixture(factory, root, monkeypatch, scenario=scenario)
        with factory() as session:
            results[scenario] = build_pilot_report(session, **inputs)["stock_model"]
        engine.dispose()
    assert results["collision"]["status"] == "ambiguous"
    assert results["collision"]["modeled_return_pct"] is None
    assert results["collision"]["conservative_return_pct"] is not None
    assert results["gap"]["events"][0]["at_price"] == "150"
    loss = results["loss20"]["events"][0]
    assert loss["event"] == "conditional_loss_exit"
    assert loss["signal_at"].startswith("2025-08-26T16:00")
    assert loss["at"].startswith("2025-08-27T09:30")
    assert results["profitable"]["status"] == "open"
    assert results["profitable"]["modeled_return_pct"] is None


def test_ambiguous_twenty_days_needs_explicit_research_interpretation(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture
    from sqlalchemy import select

    from scanner.hebeltrader.eodhd import canonical, sha
    from scanner.hebeltrader.models import Document
    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    spec = next(iter(inputs["rules"].values()))
    with sessions.begin() as session:
        doc = session.scalar(select(Document))
        pages = deepcopy(doc.pages)
        text = pages[0]["text"].replace("Kalendertagen", "Tagen")
        pages[0]["text"] = text
        pages[0]["regions"][0][0]["text"] = text.split("\n")[0]
        doc.pages = pages
    spec["evidence"][0]["quote"] = spec["evidence"][0]["quote"].replace("Kalendertagen", "Tagen")
    inputs["projection_review"]["rule_spec_sha256"] = sha(canonical(spec))
    with sessions() as session:
        blocked = build_pilot_report(session, **inputs)
        assert "unverified_rule_evidence" in blocked["quality"]["blockers"]
        spec["time_unit_interpretation"] = "Synthetic manual research interpretation, calendar days"
        inputs["projection_review"]["rule_spec_sha256"] = sha(canonical(spec))
        research = build_pilot_report(session, **inputs)
        strict = build_pilot_report(session, **dict(inputs, analysis_mode="verified"))
    assert research["stock_model"]["status"] == "closed", research["quality"]
    assert "time_unit_is_research_interpretation" in research["quality"]["uncertainties"]
    assert "unverified_time_unit_interpretation" in strict["quality"]["blockers"]
    assert strict["stock_model"]["modeled_return_pct"] is None


def test_expiry_is_not_a_stock_exit_and_continuation_needs_its_own_coverage(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.pilot import CONTINUATION, build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch, scenario="profitable")
    with sessions() as session:
        base = build_pilot_report(session, **inputs)
        extended = build_pilot_report(session, **dict(inputs, end_date=CONTINUATION))
    assert base["stock_model"]["status"] == "open"
    assert base["window"]["horizon_is_not_an_exit_rule"] is True
    assert extended["window"]["scope"] == "stock_only_continuation"
    assert extended["quality"]["classification"] == "blocked"
    assert extended["stock_model"]["modeled_return_pct"] is None


def test_raw_and_normalized_prices_must_agree_even_if_all_individual_hashes_are_valid(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.eodhd import canonical, sha
    from scanner.hebeltrader.market_snapshot import snapshot_dataset
    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    bundle = inputs["bundles"][0]
    root = inputs["market_root"]
    original = (root / bundle["spec"]["file"]).read_text()
    lines = original.splitlines()
    lines = [
        line.replace(",172,180,170,175,", ",173,180,170,175,")
        if line.startswith("2025-08-06")
        else line
        for line in lines
    ]
    assert "\n".join(lines) + "\n" != original
    (root / "altered.csv").write_text("\n".join(lines) + "\n")
    frozen = snapshot_dataset(root, root / "snapshots", dict(bundle["spec"], file="altered.csv"))
    bundle["spec"] = frozen
    bundle["bundle_sha256"] = sha(
        canonical({k: v for k, v in bundle.items() if k != "bundle_sha256"})
    )
    inputs["mapping"]["853260"].update(frozen)
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert "market_archive_integrity_or_schema_failed" in report["quality"]["blockers"]
    assert report["stock_model"]["modeled_return_pct"] is None


def test_published_jnj_baseline_is_real_original_metadata_without_claimed_market_results():
    import json
    from pathlib import Path

    from scanner.hebeltrader.pilot import JNJ_SHA
    from scanner.hebeltrader.pilot_artifacts import verify_report

    prefix = Path(__file__).resolve().parents[2] / "docs" / "hebeltrader-jnj-v17-baseline"
    assert verify_report(prefix)
    report = json.loads(Path(str(prefix) + ".json").read_bytes())
    assert report["recommendation_key"] == JNJ_SHA + ":1"
    assert report["original_recommendation"]["loaded"] is True
    assert report["original_recommendation"]["original_sha_valid"] is True
    assert report["original_recommendation"]["values"]["stock_price"] == "171.04"
    assert report["original_recommendation"]["values"]["derivative_wkn"] == "HS5RMP"
    assert report["quality"]["classification"] == "blocked"
    assert report["stock_model"]["modeled_return_pct"] is None
    assert report["derivative_observations"]["return_pct"] is None
    assert report["historical_market_data"]["status"] == "not_supplied"
    assert report["price_events"] == []
    assert report["private_full_report_replay_byte_identical"] is True


def test_tampered_raw_archive_is_reported_as_invalid_not_as_unsupplied(
    sessions, tmp_path, monkeypatch
):
    from pilot_fixtures import fixture

    from scanner.hebeltrader.eodhd import read_record
    from scanner.hebeltrader.pilot import build_pilot_report

    inputs = fixture(sessions, tmp_path, monkeypatch)
    record = read_record(inputs["raw_cache"], inputs["bundles"][0]["raw_manifests"]["eod"])
    (inputs["raw_cache"] / record["raw_file"]).write_bytes(b"[]")
    with sessions() as session:
        report = build_pilot_report(session, **inputs)
    assert report["historical_market_data"]["status"] == "invalid_archive"
    assert "market_archive_integrity_or_schema_failed" in report["historical_market_data"]["issues"]
    assert "market_archive_not_supplied" not in report["historical_market_data"]["issues"]
    assert report["stock_model"]["modeled_return_pct"] is None
