import json
from datetime import UTC, datetime
from decimal import Decimal


def _bars():
    return [
        {"date": "2025-08-05", "open": "171.04", "high": "174", "low": "169", "close": "173"},
        {"date": "2025-08-06", "open": "173", "high": "191", "low": "172", "close": "190"},
        {"date": "2025-08-07", "open": "190", "high": "217", "low": "188", "close": "216"},
    ]


def _assumptions():
    return {
        "product": {
            "strike": "190",
            "maturity": "2026-01-16",
            "ratio": "0.1",
            "fx_usd_per_eur": "1.15",
            "exercise_style": "european_call",
            "currency": "EUR",
            "parameter_status": "hypothetical",
            "source_note": "Scenario inputs; no official HS5RMP termsheet available",
            "parameter_evidence": {
                "strike": {"status": "recommendation_observed", "source": "HEBELTRADER page 1"},
                "maturity": {"status": "recommendation_observed", "source": "HEBELTRADER page 1"},
                "ratio": {"status": "hypothetical", "source": "scenario assumption"},
                "fx_usd_per_eur": {"status": "hypothetical", "source": "scenario assumption"},
                "exercise_style": {"status": "hypothetical", "source": "scenario assumption"},
            },
        },
        "scenarios": {
            "conservative": {
                "assumption_status": "hypothetical",
                "source_note": "scenario bounds, not observed HS5RMP inputs",
                "volatility": "0.14",
                "rate": "0.03",
                "dividend_yield": "0.04",
                "spread_pct": "0.20",
                "gap_haircut_pct": "0.15",
            },
            "middle": {
                "assumption_status": "hypothetical",
                "source_note": "scenario bounds, not observed HS5RMP inputs",
                "volatility": "0.20",
                "rate": "0.035",
                "dividend_yield": "0.035",
                "spread_pct": "0.12",
                "gap_haircut_pct": "0.08",
            },
            "optimistic": {
                "assumption_status": "hypothetical",
                "source_note": "scenario bounds, not observed HS5RMP inputs",
                "volatility": "0.28",
                "rate": "0.04",
                "dividend_yield": "0.03",
                "spread_pct": "0.06",
                "gap_haircut_pct": "0.03",
            },
        },
        "derivative_rules": {
            "target1": "0.70",
            "target2": "2.30",
            "stop1": "0.05",
            "partial_fraction": "0.5",
            "loss_after_days": 20,
            "loss_unit": "calendar_days",
            "time_rule_status": "hypothetical_interpretation",
        },
        "underlying_levels": {"target1": "190", "target2": "216", "stop1": "160"},
    }


def test_black_scholes_merton_call_matches_reference_value():
    from scanner.hebeltrader.derivative_model import black_scholes_merton_call

    value = black_scholes_merton_call(
        spot=Decimal("100"),
        strike=Decimal("100"),
        years=Decimal("1"),
        volatility=Decimal("0.2"),
        rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        ratio=Decimal("1"),
        fx_usd_per_eur=Decimal("1"),
    )
    assert abs(value - Decimal("10.4506")) < Decimal("0.0001")


def test_three_modes_are_separate_and_model_parameters_stay_hypothetical():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    report = build_three_mode_report(
        _bars(),
        assumptions=_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    assert set(report["modes"]) == {
        "OBSERVED_DERIVATIVE",
        "MODELED_DERIVATIVE",
        "UNDERLYING_SIGNAL",
    }
    assert report["modes"]["OBSERVED_DERIVATIVE"]["status"] == "unavailable"
    assert report["modes"]["OBSERVED_DERIVATIVE"]["return_pct"] is None
    modeled = report["modes"]["MODELED_DERIVATIVE"]
    assert set(modeled["scenarios"]) == {"conservative", "middle", "optimistic"}
    assert modeled["parameter_status"] == "hypothetical"
    assert modeled["product_assumptions"]["ratio"]["status"] == "hypothetical"
    assert modeled["observed_quote_count"] == 0
    assert modeled["training_eligible"] is False
    assert all(
        item["method"] == "Black-Scholes-Merton scenario" for item in modeled["scenarios"].values()
    )
    assert all(
        item["assumptions"]["assumption_status"] == "hypothetical"
        for item in modeled["scenarios"].values()
    )
    assert all(
        "entry_ask" in item and "exit_value" in item for item in modeled["scenarios"].values()
    )
    assert all(
        {
            "modeled_bid_before_slippage",
            "additional_slippage_pct",
            "execution_bid_after_slippage",
        }.issubset(event)
        for item in modeled["scenarios"].values()
        for event in item["events"]
    )
    underlying = report["modes"]["UNDERLYING_SIGNAL"]
    assert underlying["target1"]["reached"] is True
    assert underlying["target2"]["reached"] is True
    assert underlying["max_drawdown_pct"] is not None
    assert underlying["derivative_return_pct"] is None
    assert underlying["entry_date"] == "2025-08-06"
    sensitivity = modeled["entry_price_sensitivity"]
    assert set(sensitivity["one_at_a_time_pct"]) == {
        "volatility",
        "ratio",
        "fx_usd_per_eur",
        "spread_pct",
        "rate",
        "dividend_yield",
    }
    assert sensitivity["status"] == "hypothetical"


def test_missing_product_parameters_block_model_instead_of_being_invented():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    assumptions = _assumptions()
    del assumptions["product"]["ratio"]
    report = build_three_mode_report(
        _bars(),
        assumptions=assumptions,
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    model = report["modes"]["MODELED_DERIVATIVE"]
    assert model["status"] == "blocked"
    assert model["missing_assumptions"] == ["ratio"]
    assert model["scenarios"] == {}


def test_offline_cli_evaluates_normalized_tiingo_file_without_network(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    bars = tmp_path / "jnj-normalized.json"
    bars.write_text(json.dumps({"provider": "Tiingo", "bars": _bars(), "raw_sha256": "a" * 64}))
    assumptions = tmp_path / "assumptions.json"
    assumptions.write_text(json.dumps(_assumptions()))
    output = tmp_path / "three-modes.json"
    assert (
        main(
            [
                "scenario",
                "--underlying",
                str(bars),
                "--assumptions",
                str(assumptions),
                "--publication-at",
                "2025-08-05T08:15:00+02:00",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_bytes())
    assert report["underlying_source"]["provider"] == "Tiingo"
    assert report["underlying_source"]["raw_sha256"] == "a" * 64
    assert len(report["input_sha256"]["underlying_file"]) == 64
    assert len(report["input_sha256"]["assumptions_file"]) == 64
    assert report["modes"]["MODELED_DERIVATIVE"]["status"] == "hypothetical"


def test_modeled_twenty_day_exit_is_conditional_on_loss():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    assumptions = _assumptions()
    assumptions["derivative_rules"].update(target1="9", target2="10", stop1="0.0001")
    bars = [
        {"date": "2025-08-05", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-06", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-26", "open": "165", "high": "166", "low": "164", "close": "165"},
    ]
    report = build_three_mode_report(
        bars,
        assumptions=assumptions,
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    for scenario in report["modes"]["MODELED_DERIVATIVE"]["scenarios"].values():
        assert scenario["events"][-1]["event"] == "conditional_loss_exit"
        assert scenario["events"][-1]["execution_price_source"] == (
            "same_session_modeled_bid_close_v18_compatibility"
        )


def test_split_session_blocks_modeled_derivative_until_terms_are_reconciled():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    bars = _bars()
    bars[1]["split_factor"] = "2"
    report = build_three_mode_report(
        bars,
        assumptions=_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    assert report["underlying_data_quality"]["split_sessions"] == ["2025-08-06"]
    assert report["modes"]["MODELED_DERIVATIVE"]["status"] == "blocked"
    assert report["modes"]["MODELED_DERIVATIVE"]["scenarios"] == {}
    assert (
        "split_terms_reconciliation_required"
        in report["modes"]["MODELED_DERIVATIVE"]["missing_assumptions"]
    )


def test_daily_bars_enter_only_on_first_complete_session_after_publication():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    report = build_three_mode_report(
        _bars(),
        assumptions=_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    quality = report["underlying_data_quality"]
    assert quality["excluded_publication_day"] == "2025-08-05"
    assert quality["coverage_start"] == "2025-08-06"
    assert (
        quality["entry_policy"]
        == "first complete later session; daily bars have no intraday quotes"
    )


def test_model_stops_at_maturity_and_does_not_invent_settlement():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    assumptions = _assumptions()
    assumptions["product"]["maturity"] = "2025-08-07"
    assumptions["derivative_rules"].update(target1="99", target2="100", stop1="0.0001")
    bars = _bars()
    bars[1].update(open="200", high="202", low="198", close="201")
    report = build_three_mode_report(
        bars,
        assumptions=assumptions,
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    model = report["modes"]["MODELED_DERIVATIVE"]
    assert report["underlying_data_quality"]["coverage_end"] == "2025-08-06"
    assert all(len(item["path"]) == 1 for item in model["scenarios"].values())
    assert all(
        item["status"] == "expired_without_verified_settlement"
        for item in model["scenarios"].values()
    )
    assert all(item["return_pct"] is None for item in model["scenarios"].values())


def test_dividend_events_are_reported_but_continuous_yield_remains_an_assumption():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    bars = _bars()
    bars[1]["dividend_cash"] = "1.30"
    report = build_three_mode_report(
        bars,
        assumptions=_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    assert report["underlying_data_quality"]["dividend_sessions"] == ["2025-08-06"]
    assert report["underlying_data_quality"]["dividend_treatment"] == (
        "events disclosed only; BSM uses each scenario's hypothetical continuous dividend yield"
    )


def test_bsm_fx_ratio_and_expiry_reference_cases():
    from scanner.hebeltrader.derivative_model import black_scholes_merton_call

    base = black_scholes_merton_call(
        spot="100",
        strike="100",
        years="1",
        volatility="0.2",
        rate="0.05",
        dividend_yield="0",
        ratio="1",
        fx_usd_per_eur="1",
    )
    scaled = black_scholes_merton_call(
        spot="100",
        strike="100",
        years="1",
        volatility="0.2",
        rate="0.05",
        dividend_yield="0",
        ratio="0.1",
        fx_usd_per_eur="2",
    )
    expiry = black_scholes_merton_call(
        spot="210",
        strike="190",
        years="0",
        volatility="0.2",
        rate="0.05",
        dividend_yield="0.03",
        ratio="0.1",
        fx_usd_per_eur="1.25",
    )
    assert abs(scaled - base / Decimal("20")) < Decimal("0.0000001")
    assert expiry == Decimal("1.6")


def _historical_inputs():
    sessions = {}
    for day, fx, v20, v60, v120 in (
        ("2025-08-06", "1.1546", "0.26698", "0.20906", "0.23173"),
        ("2025-08-07", "1.1550", "0.25000", "0.21000", "0.23000"),
    ):
        sessions[day] = {
            "fx": {"usd_per_eur": fx, "fixing_date": "2025-08-05"},
            "realized_volatility": {
                "20": {"status": "available", "annualized": v20},
                "60": {"status": "available", "annualized": v60},
                "120": {"status": "available", "annualized": v120},
            },
        }
    return {
        "sessions": sessions,
        "provenance": {"fx_sha256": "a" * 64, "prehistory_sha256": "b" * 64},
        "quality": {"lookahead_policy": "strict prior data"},
    }


def _historical_assumptions():
    assumptions = _assumptions()
    del assumptions["product"]["fx_usd_per_eur"]
    del assumptions["product"]["parameter_evidence"]["fx_usd_per_eur"]
    assumptions["reference_prices"] = {
        "indicative_call_price": "0.17",
        "date": "2025-08-05",
        "status": "recommendation_observed",
        "source": "HEBELTRADER page 1",
    }
    for name, window, multiplier in (
        ("conservative", "120", "0.9"),
        ("middle", "60", "1.0"),
        ("optimistic", "20", "1.1"),
    ):
        scenario = assumptions["scenarios"][name]
        scenario.pop("volatility")
        scenario.update(volatility_window=window, iv_multiplier=multiplier)
    return assumptions


def test_historical_inputs_drive_dated_fx_and_explicit_iv_scenarios():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    report = build_three_mode_report(
        _bars(),
        assumptions=_historical_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
        historical_inputs=_historical_inputs(),
    )
    modeled = report["modes"]["MODELED_DERIVATIVE"]
    assert modeled["market_input_mode"] == "point_in_time_historical"
    conservative = modeled["scenarios"]["conservative"]
    first = conservative["path"][0]["market_inputs"]
    assert first["fx_usd_per_eur"] == "1.1546"
    assert first["fx_fixing_date"] == "2025-08-05"
    assert first["realized_volatility"] == "0.23173"
    assert first["realized_volatility_window"] == "120"
    assert first["modeled_implied_volatility"] == "0.208557"
    assert first["iv_status"] == "hypothetical_multiplier_on_realized_volatility"
    assert modeled["historical_input_provenance"]["fx_sha256"] == "a" * 64


def test_entry_comparison_and_v19_sensitivity_are_explicitly_hypothetical():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    report = build_three_mode_report(
        _bars(),
        assumptions=_historical_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
        historical_inputs=_historical_inputs(),
    )
    modeled = report["modes"]["MODELED_DERIVATIVE"]
    comparison = modeled["indicative_entry_comparison"]["middle"]
    assert comparison["indicative_call_price"] == "0.17"
    assert comparison["status"] == "hypothetical_model_vs_recommendation_indication"
    assert comparison["difference_eur"] is not None
    assert comparison["modeled_entry_date"] == "2025-08-06"
    assert comparison["indicative_price_date"] == "2025-08-05"
    factors = modeled["entry_price_sensitivity"]["one_at_a_time_pct"]
    assert set(factors) == {
        "implied_volatility",
        "ratio",
        "fx_usd_per_eur",
        "spread_pct",
        "rate",
        "dividend_yield",
    }


def test_missing_historical_window_blocks_only_affected_scenario():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    inputs = _historical_inputs()
    for session in inputs["sessions"].values():
        session["realized_volatility"]["120"] = {
            "status": "insufficient_history",
            "required_returns": 120,
        }
    report = build_three_mode_report(
        _bars(),
        assumptions=_historical_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
        historical_inputs=inputs,
    )
    scenarios = report["modes"]["MODELED_DERIVATIVE"]["scenarios"]
    assert report["modes"]["MODELED_DERIVATIVE"]["status"] == "partially_blocked"
    assert scenarios["conservative"]["status"] == "blocked_missing_historical_input"
    assert scenarios["conservative"]["return_pct"] is None
    assert scenarios["middle"]["status"] != "blocked_missing_historical_input"


def test_v19_close_signal_executes_at_next_session_open_before_daily_range():
    from scanner.hebeltrader.derivative_model import build_three_mode_report

    assumptions = _historical_assumptions()
    assumptions["derivative_rules"].update(target1="99", target2="100", stop1="0.000001")
    bars = [
        {"date": "2025-08-05", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-06", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-26", "open": "165", "high": "166", "low": "164", "close": "164"},
        # The extreme range must not affect an exit already scheduled for this open.
        {"date": "2025-08-27", "open": "174.69", "high": "400", "low": "1", "close": "200"},
    ]
    inputs = _historical_inputs()
    template = inputs["sessions"]["2025-08-06"]
    inputs["sessions"] = {row["date"]: json.loads(json.dumps(template)) for row in bars[1:]}
    report = build_three_mode_report(
        bars,
        assumptions=assumptions,
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
        historical_inputs=inputs,
    )
    for scenario in report["modes"]["MODELED_DERIVATIVE"]["scenarios"].values():
        assert scenario["events"][-2]["event"] == "conditional_loss_signal"
        assert scenario["events"][-2]["date"] == "2025-08-26"
        execution = scenario["events"][-1]
        assert execution["event"] == "conditional_loss_exit"
        assert execution["date"] == "2025-08-27"
        assert execution["execution_price_source"] == "next_session_modeled_bid_open"
        assert execution["decision_uses_session_high_low"] is False
        assert execution["modeled_bid_before_slippage"] is not None
        assert execution["additional_slippage_pct"] == scenario["assumptions"]["gap_haircut_pct"]
        assert execution["modeled_bid"] == execution["execution_bid_after_slippage"]


def test_reference_exit_returns_match_hetzner_control_values():
    from scanner.hebeltrader.derivative_model import modeled_exit_execution

    conservative_old = modeled_exit_execution("1", "0.77", "0")
    conservative_next = modeled_exit_execution("1", "0.966", "0")
    middle_old = modeled_exit_execution("1", "0.8154", "0")
    middle_next = modeled_exit_execution("1", "0.9205", "0")
    assert conservative_old["return_pct"] == "-23.00"
    assert conservative_next["return_pct"] == "-3.400"
    assert middle_old["return_pct"] == "-18.4600"
    assert middle_next["return_pct"] == "-7.9500"
