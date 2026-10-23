"""V2.0 hypothetical IV-path comparison and auditable price attribution."""

from __future__ import annotations

import math
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

STRESS_FACTORS = {
    "explicit_iv_stress_minus_50": Decimal("0.50"),
    "explicit_iv_stress_minus_25": Decimal("0.75"),
    "explicit_iv_stress_neutral": Decimal("1.00"),
    "explicit_iv_stress_plus_25": Decimal("1.25"),
    "explicit_iv_stress_plus_50": Decimal("1.50"),
}
IV_PATHS = ("constant_entry_iv", "rolling_realized_volatility", *STRESS_FACTORS)


def _variant(base, mode, entry_day, stress, session_dates):
    result = dict(base)
    internal_mode = "explicit_iv_stress" if mode in STRESS_FACTORS else mode
    path = {"mode": internal_mode, "entry_date": entry_day.isoformat()}
    if mode in STRESS_FACTORS:
        if stress.get("status") != "hypothetical_explicit_stress":
            raise ValueError("IV stress path must be explicitly hypothetical")
        sessions = stress.get("sessions", 20)
        if type(sessions) is not int or sessions < 1:
            raise ValueError("IV stress sessions must be a positive integer")
        path.update(
            start_factor="1",
            end_factor=_number(STRESS_FACTORS[mode]),
            stress_sessions=sessions,
            session_dates=[day.isoformat() for day in session_dates],
            status=stress["status"],
            source_note=stress.get("source_note"),
            variant=mode,
        )
    result["_iv_path"] = path
    return result


def crr_call_value(
    *,
    spot,
    strike,
    years,
    volatility,
    rate,
    dividend_yield,
    ratio,
    fx_usd_per_eur,
    steps,
    american=False,
):
    """CRR call value with a continuous-dividend approximation."""
    values = [
        _decimal(value, positive=True)
        for value in (spot, strike, volatility, ratio, fx_usd_per_eur)
    ]
    spot, strike, volatility, ratio, fx_usd_per_eur = values
    years, rate, dividend_yield = map(_decimal, (years, rate, dividend_yield))
    if type(steps) is not int or steps < 1:
        raise ValueError("CRR steps must be a positive integer")
    if years <= 0:
        return max(spot - strike, Decimal(0)) * ratio / fx_usd_per_eur
    dt = float(years) / steps
    up = math.exp(float(volatility) * math.sqrt(dt))
    down = 1 / up
    growth = math.exp((float(rate) - float(dividend_yield)) * dt)
    probability = (growth - down) / (up - down)
    if not 0 <= probability <= 1:
        raise ValueError("CRR probability outside [0, 1]")
    discount = math.exp(-float(rate) * dt)
    s, k = float(spot), float(strike)
    option = [max(s * up**j * down ** (steps - j) - k, 0) for j in range(steps + 1)]
    for level in range(steps - 1, -1, -1):
        next_values = []
        for node in range(level + 1):
            continuation = discount * (
                probability * option[node + 1] + (1 - probability) * option[node]
            )
            if american:
                exercise = max(s * up**node * down ** (level - node) - k, 0)
                continuation = max(continuation, exercise)
            next_values.append(continuation)
        option = next_values
    return Decimal(str(option[0])) * ratio / fx_usd_per_eur


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


def _execution_attribution(
    bars, product, scenario, historical_inputs, result, attribution, partial_fraction
):
    executions = [
        event for event in result["events"] if event.get("execution_bid_after_slippage") is not None
    ]
    if not executions or not attribution or result.get("entry_ask") is None:
        return {
            "status": "unavailable_without_execution",
            "modeled_pnl_eur": None,
            "reason": "No completed hypothetical execution is available.",
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
    partial_fraction = _decimal(partial_fraction, positive=True)
    if partial_fraction >= 1:
        raise ValueError("partial fraction must be below one")
    attribution_by_day = {row["date"]: row for row in attribution}
    remaining = Decimal(1)
    legs = []
    totals = {
        key: Decimal(0)
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
    }
    exit_value = Decimal(0)
    for index, event in enumerate(executions):
        fraction = partial_fraction if event["event"] == "target1" else remaining
        if fraction <= 0 or fraction > remaining:
            raise ValueError("invalid execution position fraction")
        remaining -= fraction
        before_slippage = _decimal(event["modeled_bid_before_slippage"])
        after_slippage = _decimal(event["execution_bid_after_slippage"])
        day_row = attribution_by_day[event["date"]]
        day_fair = _decimal(day_row["modeled_fair_value_eur"])
        # A target execution occurs at a derivative bid level, not necessarily at the close.
        # Preserve the independently calculated one-factor effects and put the exact
        # event-level difference into the disclosed nonlinear interaction residual.
        exit_fair = before_slippage / (1 - _decimal(scenario["spread_pct"]) / 2)
        fair_components = {key: _decimal(value) for key, value in day_row["components_eur"].items()}
        fair_components["interaction"] += exit_fair - day_fair
        components = fair_components | {
            "entry_spread": entry_fair - entry_ask,
            "exit_spread": before_slippage - exit_fair,
            "additional_slippage": after_slippage - before_slippage,
        }
        weighted = {key: value * fraction for key, value in components.items()}
        for key, value in weighted.items():
            totals[key] += value
        leg_pnl = fraction * (after_slippage - entry_ask)
        exit_value += fraction * after_slippage
        legs.append(
            {
                "leg": index + 1,
                "event": event["event"],
                "date": event["date"],
                "position_fraction": _number(fraction),
                "remaining_fraction": _number(remaining),
                "modeled_exit_fair_value_eur": _number(exit_fair),
                "modeled_bid_before_slippage_eur": _number(before_slippage),
                "modeled_bid_after_slippage_eur": _number(after_slippage),
                "weighted_pnl_eur": _number(leg_pnl),
                "weighted_components_eur": {key: _number(value) for key, value in weighted.items()},
            }
        )
    realized_cost = entry_ask * (Decimal(1) - remaining)
    realized_pnl = exit_value - realized_cost
    total_components = sum(totals.values(), Decimal(0))
    if abs(total_components - realized_pnl) > Decimal("1e-18"):
        raise ArithmeticError("multi-leg execution attribution does not reconcile")
    closed = remaining == 0
    return {
        "status": (
            "hypothetical_execution_pnl_attribution"
            if closed
            else "hypothetical_realized_legs_open_remainder"
        ),
        "position_closed": closed,
        "open_position_fraction": _number(remaining),
        "modeled_pnl_eur": _number(realized_pnl) if closed else None,
        "realized_legs_pnl_eur": _number(realized_pnl),
        "reconciled_total_return_pct": (
            _number(realized_pnl / entry_ask * 100) if closed else None
        ),
        "entry_fair_value_eur": _number(entry_fair),
        "entry_ask_eur": _number(entry_ask),
        "legs": legs,
        "components_eur": {key: _number(value) for key, value in totals.items()},
        "caveat": (
            "Weighted hypothetical BSM execution bridge. Open remainder is not marked to an "
            "invented closing quote; no observed HS5RMP quote is used."
        ),
    }


def _product_sensitivity(product, scenario, entry_bar, historical_inputs, indication, config):
    resolved_product, resolved_scenario, market = _resolve_market_inputs(
        product, scenario, entry_bar["date"], historical_inputs
    )
    maturity = date.fromisoformat(product["maturity"])
    years = Decimal((maturity - entry_bar["date"]).days) / Decimal(365)
    ratios = config.get("ratio_sensitivity", ["0.01", "0.05", "0.1", "0.2"])
    steps = config.get("crr_steps", 500)
    baseline = _price(
        resolved_product,
        resolved_scenario,
        spot=entry_bar["open"],
        day=entry_bar["date"],
        volatility=resolved_scenario["volatility"],
        fx=resolved_product["fx_usd_per_eur"],
    )
    spread = _decimal(scenario["spread_pct"])
    baseline_ask = baseline * (1 + spread / 2)
    rows = []
    for ratio_value in ratios:
        ratio = _decimal(ratio_value, positive=True)
        candidate = dict(resolved_product, ratio=_number(ratio))
        fair = _price(
            candidate,
            resolved_scenario,
            spot=entry_bar["open"],
            day=entry_bar["date"],
            volatility=resolved_scenario["volatility"],
            fx=resolved_product["fx_usd_per_eur"],
        )
        ask = fair * (1 + spread / 2)
        rows.append(
            {
                "ratio": _number(ratio),
                "modeled_entry_ask_eur": _number(ask),
                "difference_to_indication_eur": _number(ask - indication),
                "difference_to_current_model_eur": _number(ask - baseline_ask),
                "status": "hypothetical_ratio_sensitivity_not_product_terms",
            }
        )
    common = dict(
        spot=entry_bar["open"],
        strike=product["strike"],
        years=years,
        volatility=resolved_scenario["volatility"],
        rate=scenario["rate"],
        dividend_yield=scenario["dividend_yield"],
        ratio=product["ratio"],
        fx_usd_per_eur=resolved_product["fx_usd_per_eur"],
        steps=steps,
    )
    bsm = baseline
    european = crr_call_value(**common, american=False)
    american = crr_call_value(**common, american=True)
    return {
        "status": "hypothetical_product_parameter_sensitivity",
        "market_inputs": market,
        "ratio_sensitivity": rows,
        "binomial_comparison": {
            "steps": steps,
            "continuous_dividend_yield_approximation": str(scenario["dividend_yield"]),
            "bsm_european_call_eur": _number(bsm),
            "crr_european_call_eur": _number(european),
            "crr_american_call_eur": _number(american),
            "american_exercise_is_verified_for_hs5rmp": False,
        },
        "calibration_performed": False,
    }


def render_v20_markdown(report):
    """Render a compact deterministic human review report."""
    quality = report["base_v19_report"]["underlying_data_quality"]
    lines = [
        "# HEBELTRADER HS5RMP – hypothetische V2.0-Modellanalyse",
        "",
        "> Keine beobachteten HS5RMP-Geld-/Briefkurse und keine erzielte Rendite. "
        "Alle Optionsscheinwerte und Ausführungen sind hypothetische Modellwerte.",
        "",
        "## Historische Datenqualität",
        "",
        (
            f"- Sitzungen: {quality['bar_count']} "
            f"({quality['coverage_start']} bis {quality['coverage_end']})"
        ),
        f"- Einstiegspolitik: {quality['entry_policy']}",
        f"- Datenumfang: {quality['price_scope']}",
        "",
        "## IV-Pfade und Handelsergebnisse",
        "",
        "| Szenario | IV-Pfad | Einstieg Ask | Exitwert | Rendite | Ereignisse |",
        "|---|---|---:|---:|---:|---|",
    ]
    for scenario, scenario_data in report["scenario_analysis"].items():
        for path_name, path_data in scenario_data["iv_paths"].items():
            result = path_data["baseline_slippage"]
            events = ", ".join(f"{e['event']} {e['date']}" for e in result["events"]) or "keine"
            lines.append(
                f"| {scenario} | {path_name} | {result.get('entry_ask') or 'n/a'} | "
                f"{result.get('exit_value') or 'offen'} | "
                f"{result.get('return_pct') or 'offen'} | {events} |"
            )
    lines.extend(["", "## Slippage, Zerlegung und Strategievergleich", ""])
    lines.append(
        "Jeder IV-Pfad enthält getrennte Läufe für 0 %, Baseline und Stress-Slippage, eine "
        "gewichtete Attribution je Verkauf sowie die separate Forschungsstrategie "
        "`hold_after_loss_signal`. Offene Restpositionen werden nicht künstlich geschlossen."
    )
    lines.extend(["", "## Produktparameter-Sensitivität", ""])
    lines.append(
        "Bezugsverhältnisse 0,01/0,05/0,1/0,2 sowie europäische und amerikanische "
        "CRR-Calls werden separat verglichen. Die Dividendenrendite ist eine kontinuierliche "
        "Modellannahme; Ausübungsart und Bezugsverhältnis von HS5RMP sind nicht verifiziert."
    )
    lines.extend(["", "## Modellgrenzen und offene Datenprobleme", ""])
    for item in report["unverified_product_data"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


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
            scenario = _variant(
                base_scenario,
                mode,
                normalized[0]["date"],
                stress,
                [row["date"] for row in normalized],
            )
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
                    rules["partial_fraction"],
                ),
            }
        analysis[name] = {
            "iv_paths": path_results,
            "product_sensitivity": _product_sensitivity(
                product,
                base_scenario,
                normalized[0],
                historical_inputs,
                _decimal(assumptions["reference_prices"]["indicative_call_price"], positive=True),
                config,
            ),
        }
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
        "unverified_product_data": [
            "HS5RMP Bezugsverhältnis",
            "HS5RMP europäische oder amerikanische Ausübungsart",
            "historische HS5RMP Geld-/Briefkurse und ausführbarer Einstieg zu 0,17 EUR",
            "offizielle Abrechnungs- und letzte Handelsbedingungen",
            "historische implizite Volatilität von HS5RMP",
        ],
        "caveat": (
            "All derivative prices, executions and attributions are hypothetical BSM research; "
            "no observed or achieved HS5RMP return is claimed."
        ),
    }
