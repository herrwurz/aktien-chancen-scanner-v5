import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tests.hebeltrader.test_derivative_model import _historical_assumptions


def _bars():
    return [
        {"date": "2025-08-05", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-06", "open": "171", "high": "172", "low": "170", "close": "171"},
        {"date": "2025-08-26", "open": "165", "high": "166", "low": "164", "close": "164"},
        {"date": "2025-08-27", "open": "174.69", "high": "176", "low": "173", "close": "175"},
        {"date": "2025-08-28", "open": "175", "high": "177", "low": "174", "close": "176"},
    ]


def _market_inputs():
    sessions = {}
    for index, row in enumerate(_bars()[1:]):
        sessions[row["date"]] = {
            "fx": {
                "usd_per_eur": str(Decimal("1.1546") + Decimal(index) / 1000),
                "fixing_date": "2025-08-05",
            },
            "realized_volatility": {
                "20": {
                    "status": "available",
                    "annualized": str(Decimal("0.28") - Decimal(index) / 100),
                },
                "60": {
                    "status": "available",
                    "annualized": str(Decimal("0.22") - Decimal(index) / 200),
                },
                "120": {
                    "status": "available",
                    "annualized": str(Decimal("0.24") - Decimal(index) / 300),
                },
            },
        }
    return {"sessions": sessions, "quality": {}, "provenance": {"fixture": "synthetic"}}


def _assumptions():
    assumptions = _historical_assumptions()
    assumptions["derivative_rules"].update(target1="99", target2="100", stop1="0.000001")
    assumptions["v20_analysis"] = {
        "iv_stress_path": {
            "start_date": "2025-08-06",
            "end_date": "2025-08-27",
            "start_factor": "1",
            "end_factor": "0.5",
            "status": "hypothetical_explicit_stress",
        },
        "slippage": {
            "zero": "0",
            "stress": "0.25",
            "stress_rationale": "25% illiquidity bound for model research; not observed",
        },
    }
    return assumptions


def _report():
    from scanner.hebeltrader.derivative_v20 import build_v20_report

    return build_v20_report(
        _bars(),
        assumptions=_assumptions(),
        publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
        historical_inputs=_market_inputs(),
    )


def test_three_iv_paths_share_non_iv_inputs_and_diverge_only_after_entry():
    report = _report()
    analysis = report["scenario_analysis"]["middle"]
    assert set(analysis["iv_paths"]) == {
        "constant_entry_iv",
        "rolling_realized_volatility",
        "explicit_iv_stress",
    }
    paths = analysis["iv_paths"]
    entry_ivs = {
        value["baseline_slippage"]["path"][0]["market_inputs"]["modeled_implied_volatility"]
        for value in paths.values()
    }
    assert len(entry_ivs) == 1
    constant_rows = paths["constant_entry_iv"]["baseline_slippage"]["path"]
    stress_rows = paths["explicit_iv_stress"]["baseline_slippage"]["path"]
    assert constant_rows[-1]["market_inputs"]["modeled_implied_volatility"] == next(iter(entry_ivs))
    assert Decimal(stress_rows[-1]["market_inputs"]["modeled_implied_volatility"]) < Decimal(
        next(iter(entry_ivs))
    )
    assert constant_rows[-1]["market_inputs"]["iv_status"] == ("constant_hypothetical_entry_iv")
    assert stress_rows[-1]["market_inputs"]["iv_status"] == ("hypothetical_explicit_iv_stress_path")
    assert stress_rows[-1]["market_inputs"]["iv_basis_realized_volatility"] == "0.22"
    controlled = {
        json.dumps(value["controlled_inputs"], sort_keys=True) for value in paths.values()
    }
    assert len(controlled) == 1


def test_price_change_attribution_reconciles_stock_time_iv_fx_and_interaction():
    report = _report()
    rows = report["scenario_analysis"]["optimistic"]["iv_paths"]["explicit_iv_stress"][
        "attribution"
    ]
    assert rows
    for row in rows:
        components = row["components_eur"]
        total = sum(
            Decimal(components[key]) for key in ("stock", "time", "iv", "fx", "interaction")
        )
        assert abs(total - Decimal(row["modeled_fair_value_change_eur"])) < Decimal("1e-20")
        assert row["status"] == "hypothetical_bsm_one_factor_attribution"
    execution = report["scenario_analysis"]["middle"]["iv_paths"]["rolling_realized_volatility"][
        "execution_attribution"
    ]
    components = execution["components_eur"]
    total = sum(
        Decimal(components[key])
        for key in (
            "stock",
            "time",
            "iv",
            "fx",
            "interaction",
            "entry_spread",
            "exit_spread",
            "additional_slippage",
        )
    )
    assert abs(total - Decimal(execution["modeled_pnl_eur"])) < Decimal("1e-20")
    assert execution["status"] == "hypothetical_execution_pnl_attribution"


def test_slippage_and_loss_rule_strategies_are_separate_research_results():
    report = _report()
    item = report["scenario_analysis"]["middle"]["iv_paths"]["rolling_realized_volatility"]
    assert set(item["slippage_paths"]) == {"zero", "baseline", "stress"}
    zero = item["slippage_paths"]["zero"]
    baseline = item["slippage_paths"]["baseline"]
    stress = item["slippage_paths"]["stress"]
    assert Decimal(zero["return_pct"]) > Decimal(baseline["return_pct"])
    assert Decimal(baseline["return_pct"]) > Decimal(stress["return_pct"])
    assert zero["events"][-1]["additional_slippage_pct"] == "0"
    assert stress["events"][-1]["additional_slippage_pct"] == "0.25"
    assert baseline["events"][-2]["event"] == "conditional_loss_signal"
    assert baseline["events"][-1]["execution_price_source"] == "next_session_modeled_bid_open"
    hold = item["hold_after_loss_signal"]
    assert hold["strategy_status"] == "separate_hypothetical_research_strategy"
    assert any(event["event"] == "conditional_loss_signal" for event in hold["result"]["events"])
    assert all(event["event"] != "conditional_loss_exit" for event in hold["result"]["events"])


def test_indicative_price_is_a_reference_and_never_a_calibration_target():
    report = _report()
    reference = report["indicative_entry_reference"]
    assert reference["price_eur"] == "0.17"
    assert reference["calibration_performed"] is False
    assert reference["status"] == "recommendation_indication_not_executable_quote"
    assert set(reference["model_comparisons"]) == {"conservative", "middle", "optimistic"}
    assert (
        reference["model_comparisons"]["middle"]["rolling_realized_volatility"]["difference_eur"]
        is not None
    )
    assert report["observed_hs5rmp_quotes_used"] is False


def test_v20_refuses_to_bypass_v19_product_or_split_blockers():
    from scanner.hebeltrader.derivative_v20 import build_v20_report

    bars = _bars()
    bars[1]["split_factor"] = "2"
    with pytest.raises(ValueError, match="V1.9 model is not ready"):
        build_v20_report(
            bars,
            assumptions=_assumptions(),
            publication_at=datetime(2025, 8, 5, 6, 15, tzinfo=UTC),
            historical_inputs=_market_inputs(),
        )


def test_repository_v20_assumptions_label_stress_and_do_not_replace_v19_file():
    v19 = json.loads(
        Path("docs/hebeltrader-hs5rmp-model-assumptions-v19.example.json").read_bytes()
    )
    v20 = json.loads(
        Path("docs/hebeltrader-hs5rmp-model-assumptions-v20.example.json").read_bytes()
    )
    assert "v20_analysis" not in v19
    assert v20["v20_analysis"]["iv_stress_path"]["status"] == ("hypothetical_explicit_stress")
    assert v20["v20_analysis"]["slippage"]["zero"] == "0"
    assert v20["v20_analysis"]["slippage"]["stress"] == "0.25"
    assert v20["reference_prices"]["indicative_call_price"] == "0.17"
