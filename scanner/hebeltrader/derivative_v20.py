"""V2.0 hypothetical IV-path comparison and BSM price attribution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .derivative_model import (
    _decimal,
    _normalize_bars,
    _number,
    _resolve_market_inputs,
    _scenario,
    black_scholes_merton_call,
    build_three_mode_report,
)

IV_PATHS = ("constant_entry_iv", "rolling_realized_volatility", "explicit_iv_stress")


def _variant(base, mode, entry_day, stress):
    result = dict(base)
    path = {"mode": mode, "entry_date": entry_day.isoformat()}
    if mode == "explicit_iv_stress":
        if stress.get("status") != "hypothetical_explicit_stress":
            raise ValueError("IV stress path must be explicitly hypothetical")
        path.update(stress)
    result["_iv_path"] = path
    return result


def _price(product, scenario, *, spot, day, volatility, fx):
    maturity = date.fromisoformat(product["maturity"])
    years = Decimal(max((maturity - day).days, 0)) / Decimal(365)
    return black_scholes_merton_call(
        spot=spot,
        strike=product["strike"],
        years=years,
        volatility=volatility,
        rate=scenario["rate"],
        dividend_yield=scenario["dividend_yield"],
        ratio=product["ratio"],
        fx_usd_per_eur=fx,
    )


def _attribution(bars, product, scenario, historical_inputs, result):
    by_day = {row["date"]: row for row in bars}
    entry_bar = bars[0]
    entry_product, entry_scenario, _ = _resolve_market_inputs(
        product, scenario, entry_bar["date"], historical_inputs
    )
    entry_spot = entry_bar["open"]
    entry_iv = entry_scenario["volatility"]
    entry_fx = entry_product["fx_usd_per_eur"]
    baseline = _price(
        entry_product,
        entry_scenario,
        spot=entry_spot,
        day=entry_bar["date"],
        volatility=entry_iv,
        fx=entry_fx,
    )
    rows = []
    for path_row in result["path"]:
        day = date.fromisoformat(path_row["date"])
        bar = by_day[day]
        point = "open" if path_row.get("path_scope", "").startswith("open only") else "close"
        spot = bar[point]
        current_product, current_scenario, market = _resolve_market_inputs(
            product, scenario, day, historical_inputs
        )
        current_iv = current_scenario["volatility"]
        current_fx = current_product["fx_usd_per_eur"]
        actual = _price(
            current_product,
            current_scenario,
            spot=spot,
            day=day,
            volatility=current_iv,
            fx=current_fx,
        )
        stock = (
            _price(
                entry_product,
                entry_scenario,
                spot=spot,
                day=entry_bar["date"],
                volatility=entry_iv,
                fx=entry_fx,
            )
            - baseline
        )
        time = (
            _price(
                entry_product,
                entry_scenario,
                spot=entry_spot,
                day=day,
                volatility=entry_iv,
                fx=entry_fx,
            )
            - baseline
        )
        iv = (
            _price(
                entry_product,
                entry_scenario,
                spot=entry_spot,
                day=entry_bar["date"],
                volatility=current_iv,
                fx=entry_fx,
            )
            - baseline
        )
        fx = (
            _price(
                entry_product,
                entry_scenario,
                spot=entry_spot,
                day=entry_bar["date"],
                volatility=entry_iv,
                fx=current_fx,
            )
            - baseline
        )
        change = actual - baseline
        interaction = change - stock - time - iv - fx
        rows.append(
            {
                "date": day.isoformat(),
                "price_point": point,
                "modeled_fair_value_eur": _number(actual),
                "modeled_fair_value_change_eur": _number(change),
                "components_eur": {
                    "stock": _number(stock),
                    "time": _number(time),
                    "iv": _number(iv),
                    "fx": _number(fx),
                    "interaction": _number(interaction),
                },
                "market_inputs": market,
                "status": "hypothetical_bsm_one_factor_attribution",
                "method_note": (
                    "Each named factor is changed alone from entry; interaction is the exact "
                    "residual and includes nonlinear/order effects."
                ),
            }
        )
    return rows


def _execution_attribution(bars, product, scenario, historical_inputs, result, attribution):
    executions = [
        event for event in result["events"] if event.get("execution_bid_after_slippage") is not None
    ]
    if len(executions) != 1 or not attribution or result.get("entry_ask") is None:
        return {
            "status": "unavailable_for_multi_leg_or_open_path",
            "modeled_pnl_eur": None,
            "reason": "A single completed execution is required for exact per-unit reconciliation.",
        }
    entry_bar = bars[0]
    entry_product, entry_scenario, _ = _resolve_market_inputs(
        product, scenario, entry_bar["date"], historical_inputs
    )
    entry_fair = _price(
        entry_product,
        entry_scenario,
        spot=entry_bar["open"],
        day=entry_bar["date"],
        volatility=entry_scenario["volatility"],
        fx=entry_product["fx_usd_per_eur"],
    )
    entry_ask = _decimal(result["entry_ask"], positive=True)
    final_fair = _decimal(attribution[-1]["modeled_fair_value_eur"])
    event = executions[0]
    before_slippage = _decimal(event["modeled_bid_before_slippage"])
    after_slippage = _decimal(event["execution_bid_after_slippage"])
    fair_components = {
        key: _decimal(value) for key, value in attribution[-1]["components_eur"].items()
    }
    components = fair_components | {
        "entry_spread": entry_fair - entry_ask,
        "exit_spread": before_slippage - final_fair,
        "additional_slippage": after_slippage - before_slippage,
    }
    return {
        "status": "hypothetical_execution_pnl_attribution",
        "modeled_pnl_eur": _number(after_slippage - entry_ask),
        "entry_fair_value_eur": _number(entry_fair),
        "entry_ask_eur": _number(entry_ask),
        "exit_fair_value_eur": _number(final_fair),
        "exit_bid_before_slippage_eur": _number(before_slippage),
        "exit_bid_after_slippage_eur": _number(after_slippage),
        "components_eur": {key: _number(value) for key, value in components.items()},
        "caveat": "Per-unit hypothetical BSM and execution bridge; no observed HS5RMP quote.",
    }


def build_v20_report(bars, *, assumptions, publication_at, historical_inputs):
    if historical_inputs is None:
        raise ValueError("V2.0 requires historical market inputs")
    base = build_three_mode_report(
        bars,
        assumptions=assumptions,
        publication_at=publication_at,
        historical_inputs=historical_inputs,
    )
    if base["modes"]["MODELED_DERIVATIVE"]["status"] != "hypothetical":
        raise ValueError("V1.9 model is not ready for V2.0 analysis")
    maturity = date.fromisoformat(assumptions["product"]["maturity"])
    coverage_reaches_maturity = any(row["date"] >= maturity for row in _normalize_bars(bars))
    normalized = [
        row for row in _normalize_bars(bars) if publication_at.date() < row["date"] < maturity
    ]
    if not normalized:
        raise ValueError("no V2.0 model sessions")
    config = assumptions.get("v20_analysis", {})
    stress = config.get("iv_stress_path", {})
    slippage = config.get("slippage", {})
    if not {"zero", "stress", "stress_rationale"}.issubset(slippage):
        raise ValueError("incomplete V2.0 slippage assumptions")
    product = assumptions["product"]
    rules = assumptions["derivative_rules"]
    analysis = {}
    for name, base_scenario in assumptions["scenarios"].items():
        path_results = {}
        for mode in IV_PATHS:
            scenario = _variant(base_scenario, mode, normalized[0]["date"], stress)
            slippage_results = {}
            for label, value in (
                ("zero", slippage["zero"]),
                ("baseline", base_scenario["gap_haircut_pct"]),
                ("stress", slippage["stress"]),
            ):
                candidate = dict(scenario, gap_haircut_pct=value)
                slippage_results[label] = _scenario(
                    name,
                    normalized,
                    product,
                    candidate,
                    rules,
                    historical_inputs=historical_inputs,
                    coverage_reaches_maturity=coverage_reaches_maturity,
                )
            baseline_result = slippage_results["baseline"]
            hold_result = _scenario(
                name,
                normalized,
                product,
                scenario,
                rules,
                historical_inputs=historical_inputs,
                loss_signal_policy="hold",
                coverage_reaches_maturity=coverage_reaches_maturity,
            )
            attribution = _attribution(
                normalized, product, scenario, historical_inputs, baseline_result
            )
            path_results[mode] = {
                "controlled_inputs": {
                    key: base_scenario[key]
                    for key in ("rate", "dividend_yield", "spread_pct", "gap_haircut_pct")
                }
                | {"rules": rules, "underlying_and_fx": "identical SHA-bound V1.9 inputs"},
                "baseline_slippage": baseline_result,
                "slippage_paths": slippage_results,
                "slippage_stress_rationale": slippage["stress_rationale"],
                "hold_after_loss_signal": {
                    "strategy_status": "separate_hypothetical_research_strategy",
                    "result": hold_result,
                },
                "attribution": attribution,
                "execution_attribution": _execution_attribution(
                    normalized,
                    product,
                    scenario,
                    historical_inputs,
                    baseline_result,
                    attribution,
                ),
            }
        analysis[name] = {"iv_paths": path_results}
    reference = assumptions.get("reference_prices", {})
    indication = _decimal(reference.get("indicative_call_price"), positive=True)
    comparisons = {}
    for scenario_name, scenario_analysis in analysis.items():
        comparisons[scenario_name] = {}
        for mode, path_analysis in scenario_analysis["iv_paths"].items():
            entry = _decimal(path_analysis["baseline_slippage"]["entry_ask"], positive=True)
            comparisons[scenario_name][mode] = {
                "modeled_entry_ask": _number(entry),
                "difference_eur": _number(entry - indication),
                "difference_pct": _number((entry - indication) / indication * 100),
                "calibration_performed": False,
            }
    return {
        "status": "hypothetical_v20_iv_attribution",
        "format_version": 2,
        "observed_hs5rmp_quotes_used": False,
        "base_v19_report": base,
        "scenario_analysis": analysis,
        "indicative_entry_reference": {
            "price_eur": str(reference.get("indicative_call_price")),
            "date": reference.get("date"),
            "status": "recommendation_indication_not_executable_quote",
            "calibration_performed": False,
            "model_comparisons": comparisons,
        },
        "caveat": (
            "All derivative prices, executions and attributions are hypothetical BSM research; "
            "no observed or achieved HS5RMP return is claimed."
        ),
    }
