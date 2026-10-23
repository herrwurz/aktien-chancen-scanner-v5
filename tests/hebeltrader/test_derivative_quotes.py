"""Synthetic executable-quote fixtures; no HS5RMP historical prices are invented."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest


def quote(at, bid, ask, *, last=False):
    return {"timestamp": at, "bid": bid, "ask": ask, "last_tradable": last}


def test_offline_quote_import_is_immutable_source_bound_and_replayable(tmp_path):
    from scanner.hebeltrader.derivative_quotes import import_quote_file, read_quote_archive

    source = tmp_path / "quotes.json"
    source.write_text(
        json.dumps(
            [
                quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
                quote("2025-10-08T15:00:00+02:00", "0.71", "0.73", last=True),
            ]
        )
    )
    metadata = {
        "wkn": "HS5RMP",
        "isin": "DE000HS5RMP0",
        "venue": "XSTU",
        "timezone": "Europe/Berlin",
        "currency": "EUR",
        "source_reference": "https://example.invalid/licensed-export",
        "license": "test fixture; no redistribution",
        "retrieved_at": "2026-02-01T00:00:00+00:00",
        "coverage_start": "2025-08-05T00:00:00+02:00",
        "coverage_end": "2026-01-16T23:59:59+01:00",
        "quote_kind": "executable_bid_ask",
    }
    archive = import_quote_file(source, tmp_path / "archive", metadata=metadata)
    assert archive["raw_sha256"]
    loaded = read_quote_archive(tmp_path / "archive", archive["manifest_sha256"])
    assert loaded["quotes"][0]["ask"] == Decimal("0.18")
    assert loaded["quotes"][1]["bid"] == Decimal("0.71")
    assert import_quote_file(source, tmp_path / "archive", metadata=metadata) == archive
    source.write_text("[]")
    with pytest.raises(ValueError, match="immutable"):
        import_quote_file(source, tmp_path / "archive", metadata=metadata)


def test_derivative_backtest_uses_ask_for_entry_bid_for_exits_and_50_50():
    from scanner.hebeltrader.derivative_quotes import DerivativeRules, simulate_derivative_quotes

    quotes = [
        quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
        quote("2025-09-01T09:00:00+02:00", "0.71", "0.73"),
        quote("2025-10-01T09:00:00+02:00", "2.31", "2.35"),
    ]
    result = simulate_derivative_quotes(
        quotes,
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime(2026, 1, 16, 20, tzinfo=UTC),
        rules=DerivativeRules(
            target1=Decimal("0.70"),
            target2=Decimal("2.30"),
            stop1=Decimal("0.05"),
            partial_fraction=Decimal("0.5"),
            after_target1="entry",
            loss_after_days=20,
            loss_unit="calendar_days",
        ),
    )
    assert result["entry"]["side"] == "ask"
    assert result["entry"]["price"] == "0.18"
    assert [event["price"] for event in result["events"]] == ["0.71", "2.31"]
    assert all(event["side"] == "bid" for event in result["events"])
    assert result["return_pct"] == str(Decimal("738.8888888888888888888888889"))


def test_twenty_day_rule_is_conditional_loss_and_missing_quotes_block_return():
    from scanner.hebeltrader.derivative_quotes import DerivativeRules, simulate_derivative_quotes

    rules = DerivativeRules(
        target1=Decimal("0.70"),
        target2=Decimal("2.30"),
        stop1=Decimal("0.05"),
        loss_after_days=20,
        loss_unit="calendar_days",
    )
    result = simulate_derivative_quotes(
        [
            quote("2025-08-06T08:00:00+02:00", "0.16", "0.18"),
            quote("2025-08-27T08:00:00+02:00", "0.17", "0.19"),
            quote("2025-08-28T08:00:00+02:00", "0.15", "0.17"),
        ],
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime(2026, 1, 16, 20, tzinfo=UTC),
        rules=rules,
    )
    assert result["events"][0]["event"] == "conditional_loss_exit"
    assert result["events"][0]["price"] == "0.17"
    blocked = simulate_derivative_quotes(
        [],
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime(2026, 1, 16, 20, tzinfo=UTC),
        rules=rules,
    )
    assert blocked["return_pct"] is None
    assert blocked["status"] == "blocked"


def test_product_terms_require_source_hash_and_manual_verification():
    from scanner.hebeltrader.derivative_quotes import verify_product_terms

    candidate = {
        "wkn": "HS5RMP",
        "isin": None,
        "issuer": "HSBC",
        "ratio": None,
        "strike": None,
        "maturity": "2026-01-16",
        "last_trading_at": None,
        "settlement": None,
        "source_sha256": None,
        "source_reference": None,
        "review_status": "pending",
    }
    result = verify_product_terms(candidate)
    assert result["verified"] is False
    assert "isin" in result["missing"] and "last_trading_at" in result["missing"]
    assert {"reference_exchange", "settlement_currency", "fx_rule", "exercise"} <= set(
        result["missing"]
    )


def test_quote_archive_cannot_claim_executability_without_gap_hours_and_rights_review():
    from scanner.hebeltrader.derivative_quotes import quote_archive_ready

    metadata = {
        "completeness_status": "pending",
        "trading_hours_reference": None,
        "quote_gap_review": None,
        "usage_rights_status": "unreviewed",
        "reviewer": None,
        "reviewed_at": None,
    }
    ready = quote_archive_ready(metadata)
    assert ready["approved"] is False
    assert set(ready["missing"]) == {
        "completeness_status",
        "trading_hours_reference",
        "quote_gap_review",
        "usage_rights_status",
        "reviewer",
        "reviewed_at",
    }


def test_csv_quote_import_preserves_execution_evidence_and_replays(tmp_path):
    from scanner.hebeltrader.derivative_quotes import import_quote_file, read_quote_archive

    source = tmp_path / "authorized.csv"
    source.write_text(
        "timestamp,bid,ask,bid_size,ask_size,quote_status,last_tradable\n"
        "2025-08-06T08:01:00+02:00,0.16,0.18,1000,900,executable,false\n"
        "2025-08-06T08:02:00+02:00,0.17,0.19,800,700,executable,true\n"
    )
    metadata = _metadata()
    archive = import_quote_file(source, tmp_path / "archive", metadata=metadata)
    loaded = read_quote_archive(tmp_path / "archive", archive["manifest_sha256"])
    assert archive["format_version"] == 2
    assert loaded["quotes"][0]["bid_size"] == Decimal("1000")
    assert loaded["quotes"][0]["quote_status"] == "executable"
    assert import_quote_file(source, tmp_path / "archive", metadata=metadata) == archive


def test_import_rejects_indications_and_one_sided_quotes_as_executable(tmp_path):
    from scanner.hebeltrader.derivative_quotes import import_quote_file

    for name, row in (
        (
            "indication",
            [
                {
                    "timestamp": "2025-08-06T08:01:00+02:00",
                    "bid": "0.16",
                    "ask": "0.18",
                    "quote_status": "indicative",
                }
            ],
        ),
        ("one-sided", [{"timestamp": "2025-08-06T08:01:00+02:00", "bid": "0.16", "ask": ""}]),
    ):
        source = tmp_path / f"{name}.json"
        source.write_text(json.dumps(row))
        with pytest.raises(ValueError, match="executable|quote"):
            import_quote_file(source, tmp_path / name, metadata=_metadata())


def test_coverage_audit_reports_gaps_spreads_and_observed_levels():
    from scanner.hebeltrader.derivative_quotes import audit_quote_coverage

    quotes = [
        quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
        quote("2025-08-06T08:02:00+02:00", "0.04", "0.07"),
        quote("2025-08-08T08:02:00+02:00", "0.72", "0.75"),
    ]
    report = audit_quote_coverage(
        quotes,
        expected_start=datetime.fromisoformat("2025-08-06T08:00:00+02:00"),
        expected_end=datetime.fromisoformat("2025-08-08T09:00:00+02:00"),
        max_gap=timedelta(hours=12),
        levels={"target1": Decimal("0.70"), "stop1": Decimal("0.05")},
    )
    assert report["earliest_quote"].startswith("2025-08-06T08:01")
    assert report["latest_quote"].startswith("2025-08-08T08:02")
    assert report["complete"] is False
    assert report["missing_intervals"][0]["duration_seconds"] > 12 * 3600
    assert report["spread"]["maximum"] == "0.03"
    assert report["observed_levels"] == {"stop1": True, "target1": True}


def test_costs_whole_units_and_actual_gap_prices_are_reflected_in_cash_result():
    from scanner.hebeltrader.derivative_quotes import DerivativeRules, simulate_derivative_quotes

    result = simulate_derivative_quotes(
        [
            quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
            quote("2025-09-01T09:00:00+02:00", "0.74", "0.76"),
            quote("2025-10-01T09:00:00+02:00", "0.15", "0.17"),
        ],
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime(2026, 1, 16, 20, tzinfo=UTC),
        rules=DerivativeRules(Decimal("0.70"), Decimal("2.30"), Decimal("0.05")),
        capital=Decimal("100"),
        unit_size=1,
        fee_per_order=Decimal("1"),
    )
    assert result["position"]["units"] == 550
    assert result["events"][1]["event"] == "stop"
    assert result["events"][1]["price"] == "0.15"
    assert result["cash_result"]["fees"] == "3"
    assert result["cash_result"]["net_profit"] == "142.75"


def test_last_quote_is_not_expiry_settlement_without_separate_evidence():
    from scanner.hebeltrader.derivative_quotes import DerivativeRules, simulate_derivative_quotes

    quotes = [
        quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
        quote("2026-01-16T19:59:00+01:00", "0.10", "0.12", last=True),
    ]
    result = simulate_derivative_quotes(
        quotes,
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime.fromisoformat("2026-01-16T20:00:00+01:00"),
        rules=DerivativeRules(Decimal("0.70"), Decimal("2.30"), Decimal("0.05")),
    )
    assert result["status"] == "open_or_censored"
    assert result["return_pct"] is None
    assert result["blocker"] == "expiry_settlement_or_exit_quote_not_evidenced"


def test_quote_size_can_be_required_for_modeled_fill():
    from scanner.hebeltrader.derivative_quotes import DerivativeRules, simulate_derivative_quotes

    quotes = [
        {
            **quote("2025-08-06T08:01:00+02:00", "0.16", "0.18"),
            "bid_size": "100",
            "ask_size": "100",
        }
    ]
    result = simulate_derivative_quotes(
        quotes,
        publication_at=datetime(2025, 8, 5, tzinfo=UTC),
        last_trading_at=datetime(2026, 1, 16, 20, tzinfo=UTC),
        rules=DerivativeRules(Decimal("0.70"), Decimal("2.30"), Decimal("0.05")),
        capital=Decimal("100"),
        enforce_quote_size=True,
    )
    assert result["status"] == "blocked"
    assert result["blocker"] == "insufficient_entry_quote_size"
    assert result["return_pct"] is None


def _metadata():
    return {
        "wkn": "HS5RMP",
        "isin": "DE000HS5RMP0",
        "venue": "XSTU",
        "timezone": "Europe/Berlin",
        "currency": "EUR",
        "source_reference": "https://example.invalid/authorized-export",
        "license": "test fixture; internal research only",
        "retrieved_at": "2026-02-01T00:00:00+00:00",
        "coverage_start": "2025-08-05T00:00:00+02:00",
        "coverage_end": "2026-01-16T23:59:59+01:00",
        "quote_kind": "executable_bid_ask",
    }
