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
    underlying = report["modes"]["UNDERLYING_SIGNAL"]
    assert underlying["target1"]["reached"] is True
    assert underlying["target2"]["reached"] is True
    assert underlying["max_drawdown_pct"] is not None
    assert underlying["derivative_return_pct"] is None


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
        {"date": "2025-08-26", "open": "165", "high": "166", "low": "164", "close": "165"},
    ]
    report = build_three_mode_report(
        bars,
        assumptions=assumptions,
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
    )
    for scenario in report["modes"]["MODELED_DERIVATIVE"]["scenarios"].values():
        assert scenario["events"][-1]["event"] == "conditional_loss_exit"


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
