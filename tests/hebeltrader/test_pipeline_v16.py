"""Synthetic regression inventory; never a measurement of Hetzner coverage."""

import json

import pytest
from test_backtest_report import AS_OF, add_recommendation
from test_rules_v16 import spec_for

from scanner.hebeltrader.backtest_pipeline_v16 import (
    build_v16_report,
    verify_audit,
    write_verified_audit,
)


def test_fixed_118_synthetic_inventory_reproducible_readonly_and_not_verified(sessions, tmp_path):
    identifiers = ["578560", "SJ6B4A"] + [f"A{i:05d}" for i in range(94)]
    with sessions.begin() as session:
        for index in range(118):
            doc, rec = add_recommendation(session, index)
            rec.stock_wkn = (identifiers + identifiers[:18])[index] if index < 114 else None
            if rec.stock_wkn == "SJ6B4A":
                rec.derivative_wkn = "SJ6B4A"
    with sessions() as session:
        report = build_v16_report(session, run_at=AS_OF, as_of=AS_OF, synthetic=True)
        replay = build_v16_report(session, run_at=AS_OF, as_of=AS_OF, synthetic=True)
        assert not session.new and not session.dirty and not session.deleted
    assert report == replay
    assert report["measurement_scope"] == "synthetic"
    assert report["count"] == 118
    assert report["pipeline_summary"]["unique_wkn"] == 96
    assert report["pipeline_summary"]["missing_stock_identifiers"] == 4
    assert report["pipeline_summary"]["classification_conflicts"] == 1
    assert report["evaluation_summary"]["fully_evaluable"] == 0
    assert report["evaluation_summary"]["missing_prerequisites"] == 118
    assert report["evaluation_summary"]["confirmed_historical_successes"] is None
    a, b = tmp_path / "a", tmp_path / "b"
    left, right = write_verified_audit(a, report), write_verified_audit(b, report)
    assert [p.read_bytes() for p in left] == [p.read_bytes() for p in right]
    assert verify_audit(a) is True
    with pytest.raises(FileExistsError):
        write_verified_audit(a, report)
    left[1].write_text("changed")
    with pytest.raises(ValueError, match="integrity"):
        verify_audit(a)


def test_archive_failure_blocks_all_modes_even_with_approved_rules(sessions):
    with sessions.begin() as session:
        doc, rec = add_recommendation(session)
        rules = {f"{doc.sha256}:1": spec_for(doc, rec)}
    with sessions() as session:
        report = build_v16_report(
            session,
            run_at=AS_OF,
            as_of=AS_OF,
            rules=rules,
            expected_count=1,
            archive_audit={"errors": ["linked_candidates_mismatch"]},
        )
    assert all(not g["ready"] for g in report["results"][0]["mode_audit"].values())
    assert "openfigi_archive_integrity_failed" in report["remaining_data_gaps"]


def test_cli_v16_verify_and_readonly(sessions, tmp_path, monkeypatch):
    from sqlalchemy import event

    from scanner.hebeltrader.historical_cli import main

    with sessions.begin() as session:
        add_recommendation(session)
    engine = sessions.kw["bind"]
    statements = []
    event.listen(engine, "before_cursor_execute", lambda c, u, s, p, x, m: statements.append(s))
    monkeypatch.setattr("scanner.hebeltrader.historical_cli.create_db", lambda _: engine)
    prefix = tmp_path / "cli"
    assert (
        main(
            [
                "audit",
                "--evaluate",
                "--synthetic",
                "--run-at",
                AS_OF.isoformat(),
                "--as-of",
                AS_OF.isoformat(),
                "--output-prefix",
                str(prefix),
                "--expected-count",
                "1",
            ]
        )
        == 0
    )
    assert all(s.upper().startswith(("SELECT", "PRAGMA QUERY_ONLY=ON")) for s in statements)
    assert main(["verify", "--output-prefix", str(prefix)]) == 0
    assert json.loads((tmp_path / "cli.json").read_text())["count"] == 1


@pytest.mark.parametrize("mode", ["research", "verified"])
@pytest.mark.parametrize("ambiguous_unit", [False, True])
def test_v16_reviewed_series_reaches_engine_but_strict_availability_stays_blocked(
    sessions, tmp_path, monkeypatch, mode, ambiguous_unit
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
        from test_rules_v16 import spec_for

        approved = spec_for(doc, rec)
        approved["reviewed_at"] = CLOCK.isoformat()
        if ambiguous_unit:
            quote = approved["evidence"][0]["quote"].replace("Kalendertagen", "Tagen")
            approved["evidence"][0]["quote"] = quote
            doc.pages[0]["text"] = quote
            doc.pages[0]["regions"][0][0]["text"] = quote
            approved["time_unit_interpretation"] = "Synthetic calendar-day research assumption"

        doc.pages[0]["text"] += "\n" + header
        doc.metadata_evidence = [dict(page=3, raw=header)]
        rules = {f"{doc.sha256}:1": approved}
    with sessions() as session:
        report = build_v16_report(
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

    if ambiguous_unit:
        assert (
            "unverified_time_unit_interpretation"
            in report["results"][0]["mode_audit"]["verified"]["blockers"]
        )
    outcome = report["results"][0]["backtest"]
    if mode == "research":
        assert outcome["status"] == "ambiguous", outcome
        assert outcome["fully_evaluable"] is False
        assert outcome["modeled_entry"] == "10"
    else:
        assert outcome["status"] == "unknown"


def test_published_original_inventory_matrix_is_complete_and_provenance_bound():
    import csv
    from hashlib import sha256
    from pathlib import Path

    docs = Path(__file__).resolve().parents[2] / "docs"
    matrix = (docs / "hebeltrader-backtest-v16-matrix.csv").read_bytes()
    baseline = json.loads((docs / "hebeltrader-backtest-v16-baseline.json").read_bytes())
    assert sha256(matrix).hexdigest() == baseline["matrix_sha256"]
    rows = list(csv.DictReader(matrix.decode().splitlines()))
    assert len(rows) == 118
    assert len({(r["document_sha"], r["ordinal"]) for r in rows}) == 118
    assert len({r["stock_wkn"] for r in rows if r["stock_wkn"]}) == 96
    assert sum(not r["stock_wkn"] for r in rows) == 4
    assert all(r["status"] == "unknown" for r in rows)
    for prefix in ("0423a87f", "52e053b7", "5cf16313", "ca53f7e4", "e73f23ac"):
        assert sum(r["document_sha"].startswith(prefix) for r in rows) == 1
    assert baseline["original_pdf_sha_valid"] == 118
    assert baseline["actual_external_coverage"].startswith("unmeasured")
