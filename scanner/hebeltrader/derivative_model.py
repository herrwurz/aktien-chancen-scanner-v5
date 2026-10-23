"""Explicitly hypothetical warrant scenarios and separate underlying-signal audit."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def _decimal(value, *, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid numeric assumption") from None
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError("invalid numeric assumption")
    return result


def _number(value):
    return format(value.normalize(), "f")


def _cdf(value):
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def black_scholes_merton_call(
    *, spot, strike, years, volatility, rate, dividend_yield, ratio, fx_usd_per_eur
):
    """European call value in EUR when spot/strike are USD and FX is USD per EUR."""
    spot = _decimal(spot, positive=True)
    strike = _decimal(strike, positive=True)
    years = _decimal(years)
    volatility = _decimal(volatility)
    rate = _decimal(rate)
    dividend_yield = _decimal(dividend_yield)
    ratio = _decimal(ratio, positive=True)
    fx_usd_per_eur = _decimal(fx_usd_per_eur, positive=True)
    if years <= 0:
        return max(spot - strike, Decimal(0)) * ratio / fx_usd_per_eur
    if volatility <= 0:
        raise ValueError("volatility must be positive")
    s, k, t, sigma, r, q = map(float, (spot, strike, years, volatility, rate, dividend_yield))
    root_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + sigma * sigma / 2) * t) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    usd = s * math.exp(-q * t) * _cdf(d1) - k * math.exp(-r * t) * _cdf(d2)
    return Decimal(str(usd)) * ratio / fx_usd_per_eur


def _normalize_bars(bars):
    result = []
    seen = set()
    for row in bars:
        day = date.fromisoformat(str(row["date"])[:10])
        if day in seen:
            raise ValueError("duplicate underlying session")
        seen.add(day)
        values = {
            key: _decimal(row[key], positive=True) for key in ("open", "high", "low", "close")
        }
        if not values["low"] <= min(values["open"], values["close"]):
            raise ValueError("invalid underlying OHLC")
        if not values["high"] >= max(values["open"], values["close"]):
            raise ValueError("invalid underlying OHLC")
        result.append({"date": day, **values})
    result.sort(key=lambda row: row["date"])
    if not result:
        raise ValueError("underlying series is empty")
    return result


def _underlying_signal(bars, levels):
    entry = bars[0]["open"]
    level_values = {
        key: _decimal(levels[key], positive=True) for key in ("target1", "target2", "stop1")
    }
    peak = entry
    max_drawdown = Decimal(0)
    events = {key: None for key in level_values}
    for session, bar in enumerate(bars, 1):
        peak = max(peak, bar["high"])
        max_drawdown = max(max_drawdown, (peak - bar["low"]) / peak * 100)
        for name, value in level_values.items():
            touched = bar["high"] >= value if name.startswith("target") else bar["low"] <= value
            if touched and events[name] is None:
                events[name] = {
                    "reached": True,
                    "date": bar["date"].isoformat(),
                    "trading_sessions": session,
                    "calendar_days": (bar["date"] - bars[0]["date"]).days,
                    "level": _number(value),
                    "evidence": "underlying daily OHLC range",
                }
    return {
        "status": "historical_underlying_signal_only",
        "instrument": "JNJ stock",
        "entry_open": _number(entry),
        "entry_date": bars[0]["date"].isoformat(),
        "target1": events["target1"]
        or {"reached": False, "level": _number(level_values["target1"])},
        "target2": events["target2"]
        or {"reached": False, "level": _number(level_values["target2"])},
        "stop1": events["stop1"] or {"reached": False, "level": _number(level_values["stop1"])},
        "max_drawdown_pct": _number(max_drawdown),
        "max_drawdown_scope": (
            "conservative daily-OHLC bound; intraday high/low ordering is unknown"
        ),
        "observation_sessions": len(bars),
        "derivative_return_pct": None,
        "caveat": "Stock OHLC signal quality; no warrant execution or return claim.",
        "training_eligible": False,
    }


def _resolve_market_inputs(product, scenario, day, historical_inputs=None):
    if historical_inputs is None:
        return (
            product,
            scenario,
            {
                "fx_usd_per_eur": str(product["fx_usd_per_eur"]),
                "realized_volatility": None,
                "modeled_implied_volatility": str(scenario["volatility"]),
                "iv_status": "fixed_hypothetical_assumption",
            },
        )
    session = historical_inputs.get("sessions", {}).get(day.isoformat())
    if not session:
        raise ValueError(f"missing historical inputs for {day.isoformat()}")
    fx = session.get("fx", {})
    if not fx.get("usd_per_eur"):
        raise ValueError(f"missing prior ECB fixing for {day.isoformat()}")
    window = str(scenario.get("volatility_window", ""))
    volatility = session.get("realized_volatility", {}).get(window, {})
    if volatility.get("status") != "available" or not volatility.get("annualized"):
        raise ValueError(f"missing realized volatility window {window} for {day.isoformat()}")
    multiplier = _decimal(scenario.get("iv_multiplier"), positive=True)
    realized = _decimal(volatility["annualized"], positive=True)
    implied = realized * multiplier
    resolved_product = dict(product, fx_usd_per_eur=fx["usd_per_eur"])
    resolved_scenario = dict(scenario, volatility=_number(implied))
    return (
        resolved_product,
        resolved_scenario,
        {
            "fx_usd_per_eur": str(fx["usd_per_eur"]),
            "fx_fixing_date": fx.get("fixing_date"),
            "realized_volatility": _number(realized),
            "realized_volatility_window": window,
            "modeled_implied_volatility": _number(implied),
            "iv_multiplier": _number(multiplier),
            "iv_status": "hypothetical_multiplier_on_realized_volatility",
        },
    )


def _fair(product, scenario, spot, day, historical_inputs=None):
    product, scenario, _ = _resolve_market_inputs(product, scenario, day, historical_inputs)
    maturity = date.fromisoformat(product["maturity"])
    years = Decimal(max((maturity - day).days, 0)) / Decimal("365")
    return black_scholes_merton_call(
        spot=spot,
        strike=product["strike"],
        years=years,
        volatility=scenario["volatility"],
        rate=scenario["rate"],
        dividend_yield=scenario["dividend_yield"],
        ratio=product["ratio"],
        fx_usd_per_eur=product["fx_usd_per_eur"],
    )


def _scenario(
    name,
    bars,
    product,
    scenario,
    rules,
    *,
    coverage_reaches_maturity=False,
    historical_inputs=None,
):
    required = {
        "rate",
        "dividend_yield",
        "spread_pct",
        "gap_haircut_pct",
        "assumption_status",
        "source_note",
    }
    required |= (
        {"volatility"} if historical_inputs is None else {"volatility_window", "iv_multiplier"}
    )
    if not required.issubset(scenario) or scenario["assumption_status"] != "hypothetical":
        raise ValueError("incomplete or unlabelled scenario assumptions")
    spread = _decimal(scenario["spread_pct"])
    gap = _decimal(scenario["gap_haircut_pct"])
    if not Decimal(0) <= spread < Decimal(1) or not Decimal(0) <= gap < Decimal(1):
        raise ValueError("invalid spread or gap assumption")
    targets = {key: _decimal(rules[key], positive=True) for key in ("target1", "target2", "stop1")}
    blockers = []
    for bar in bars:
        try:
            _resolve_market_inputs(product, scenario, bar["date"], historical_inputs)
        except ValueError as exc:
            blockers.append(str(exc))
    if blockers:
        return {
            "method": "Black-Scholes-Merton scenario",
            "status": "blocked_missing_historical_input",
            "return_pct": None,
            "entry_ask": None,
            "exit_value": None,
            "events": [],
            "path": [],
            "assumptions": scenario,
            "blockers": sorted(set(blockers)),
            "collision_policy": "no execution",
        }
    fair_entry = _fair(product, scenario, bars[0]["open"], bars[0]["date"], historical_inputs)
    entry = fair_entry * (1 + spread / 2)
    if entry <= 0:
        return {
            "method": "Black-Scholes-Merton scenario",
            "status": "invalid_zero_model_entry",
            "return_pct": None,
            "entry_ask": _number(entry),
            "exit_value": None,
            "events": [],
            "path": [],
            "assumptions": scenario,
            "collision_policy": "no execution",
        }
    events = []
    first = None
    modeled_path = []
    loss_after = rules.get("loss_after_days")
    loss_unit = rules.get("loss_unit")
    for session, bar in enumerate(bars, 1):
        _, _, market_audit = _resolve_market_inputs(
            product, scenario, bar["date"], historical_inputs
        )
        fair = {
            key: _fair(product, scenario, bar[key], bar["date"], historical_inputs)
            for key in ("open", "high", "low", "close")
        }
        bid = {key: value * (1 - spread / 2) for key, value in fair.items()}
        modeled_path.append(
            {
                "date": bar["date"].isoformat(),
                "fair_close": _number(fair["close"]),
                "modeled_bid_close": _number(bid["close"]),
                "modeled_ask_close": _number(fair["close"] * (1 + spread / 2)),
                "market_inputs": market_audit,
            }
        )
        stop = entry if first is not None else targets["stop1"]
        target = targets["target2"] if first is not None else targets["target1"]
        stop_touch, target_touch = bid["low"] <= stop, bid["high"] >= target
        if stop_touch and target_touch and name == "middle":
            return {
                "method": "Black-Scholes-Merton scenario",
                "status": "ambiguous_intraday",
                "return_pct": None,
                "entry_ask": _number(entry),
                "exit_value": None,
                "events": events,
                "path": modeled_path,
                "assumptions": scenario,
                "collision_policy": "withhold result",
            }
        choose_target = target_touch and (not stop_touch or name == "optimistic")
        if choose_target:
            event = "target2" if first is not None else "target1"
            events.append(
                {"event": event, "date": bar["date"].isoformat(), "modeled_bid": _number(target)}
            )
            if first is None:
                first = target
                continue
            average = (first + target) / 2
            return _closed_scenario(name, scenario, entry, average, events, modeled_path)
        if stop_touch:
            price = min(stop, bid["open"]) * (1 - gap)
            events.append(
                {"event": "stop", "date": bar["date"].isoformat(), "modeled_bid": _number(price)}
            )
            average = price if first is None else (first + price) / 2
            return _closed_scenario(name, scenario, entry, average, events, modeled_path)
        elapsed = (bar["date"] - bars[0]["date"]).days if loss_unit == "calendar_days" else session
        if loss_after is not None and elapsed >= loss_after and bid["close"] < entry:
            price = bid["close"] * (1 - gap)
            events.append(
                {
                    "event": "conditional_loss_exit",
                    "date": bar["date"].isoformat(),
                    "modeled_bid": _number(price),
                    "elapsed": elapsed,
                    "unit": loss_unit,
                }
            )
            average = price if first is None else (first + price) / 2
            return _closed_scenario(name, scenario, entry, average, events, modeled_path)
    return {
        "method": "Black-Scholes-Merton scenario",
        "status": (
            "expired_without_verified_settlement"
            if coverage_reaches_maturity
            else "open_or_censored"
        ),
        "return_pct": None,
        "entry_ask": _number(entry),
        "exit_value": None,
        "events": events,
        "path": modeled_path,
        "assumptions": scenario,
        "collision_policy": "stop first" if name == "conservative" else "target first",
    }


def _entry_sensitivity(bar, product, scenario, historical_inputs=None):
    """One-at-a-time entry-ask sensitivity around the middle hypothetical case."""
    product, scenario, market_audit = _resolve_market_inputs(
        product, scenario, bar["date"], historical_inputs
    )
    spread = _decimal(scenario["spread_pct"])

    def entry(candidate_product, candidate_scenario):
        fair = _fair(candidate_product, candidate_scenario, bar["open"], bar["date"])
        return fair * (1 + _decimal(candidate_scenario["spread_pct"]) / 2)

    base = entry(product, scenario)
    results = {}
    fields = (
        "implied_volatility" if historical_inputs is not None else "volatility",
        "ratio",
        "fx_usd_per_eur",
        "spread_pct",
        "rate",
        "dividend_yield",
    )
    for field in fields:
        values = {}
        for label, multiplier in (("minus_10pct", Decimal("0.9")), ("plus_10pct", Decimal("1.1"))):
            candidate_product = dict(product)
            candidate_scenario = dict(scenario)
            actual_field = "volatility" if field == "implied_volatility" else field
            destination = (
                candidate_product if field in {"ratio", "fx_usd_per_eur"} else candidate_scenario
            )
            destination[actual_field] = _number(_decimal(destination[actual_field]) * multiplier)
            value = entry(candidate_product, candidate_scenario)
            values[label] = {
                "entry_ask": _number(value),
                "change_pct": _number((value - base) / base * 100) if base else None,
            }
        results[field] = values
    return {
        "status": "hypothetical",
        "method": "one-at-a-time +/-10% around middle scenario",
        "base_entry_ask": _number(base),
        "base_spread_pct": _number(spread),
        "base_market_inputs": market_audit,
        "one_at_a_time_pct": results,
        "caveat": "Local model sensitivity, not confidence bounds or observed HS5RMP prices.",
    }


def _closed_scenario(name, assumptions, entry, exit_value, events, path):
    return {
        "method": "Black-Scholes-Merton scenario",
        "status": "hypothetical_closed",
        "return_pct": _number((exit_value - entry) / entry * 100),
        "entry_ask": _number(entry),
        "exit_value": _number(exit_value),
        "events": events,
        "path": path,
        "assumptions": assumptions,
        "collision_policy": "stop first" if name == "conservative" else "target first",
    }


def _entry_comparison(scenario, indication, reference):
    modeled = _decimal(scenario["entry_ask"], positive=True)
    difference = modeled - indication
    return {
        "modeled_entry_ask": _number(modeled),
        "indicative_call_price": _number(indication),
        "difference_eur": _number(difference),
        "difference_pct": _number(difference / indication * 100),
        "status": "hypothetical_model_vs_recommendation_indication",
        "reference_status": reference.get("status"),
        "reference_source": reference.get("source"),
    }


def build_three_mode_report(
    bars,
    *,
    assumptions,
    publication_at,
    observed_derivative=None,
    historical_inputs=None,
):
    if not isinstance(publication_at, datetime) or publication_at.utcoffset() is None:
        raise ValueError("publication timestamp with timezone required")
    split_sessions = [
        str(row["date"])[:10]
        for row in bars
        if _decimal(row.get("split_factor", "1"), positive=True) != Decimal(1)
    ]
    dividend_sessions = [
        str(row["date"])[:10]
        for row in bars
        if _decimal(row.get("dividend_cash", "0")) != Decimal(0)
    ]
    all_normalized = _normalize_bars(bars)
    # EOD bars cannot establish an executable price after an intraday publication.
    # Start at the first complete later session, regardless of the publication clock.
    normalized = [row for row in all_normalized if row["date"] > publication_at.date()]
    if not normalized:
        raise ValueError("no complete underlying session after publication")
    product = assumptions.get("product", {})
    required = [
        "strike",
        "maturity",
        "ratio",
        "exercise_style",
        "parameter_status",
        "source_note",
    ]
    if historical_inputs is None:
        required.append("fx_usd_per_eur")
    missing = [key for key in required if not product.get(key)]
    maturity = None
    if product.get("maturity"):
        try:
            maturity = date.fromisoformat(product["maturity"])
        except (TypeError, ValueError):
            missing.append("maturity:invalid")
    coverage_reaches_maturity = False
    if maturity is not None:
        # Maturity is not evidence of the last tradable instant or settlement terms.
        coverage_reaches_maturity = any(row["date"] >= maturity for row in normalized)
        normalized = [row for row in normalized if row["date"] < maturity]
        if not normalized:
            raise ValueError("no complete tradable session between publication and maturity")
    if split_sessions:
        missing.append("split_terms_reconciliation_required")
    evidence = product.get("parameter_evidence", {})
    evidence_keys = ["strike", "maturity", "ratio", "exercise_style"]
    if historical_inputs is None:
        evidence_keys.append("fx_usd_per_eur")
    for key in evidence_keys:
        if not isinstance(evidence.get(key), dict) or not evidence[key].get("status"):
            missing.append(f"parameter_evidence:{key}")
    modeled = {
        "status": "blocked" if missing else "hypothetical",
        "parameter_status": product.get("parameter_status"),
        "product_assumptions": evidence,
        "product_inputs": {key: product.get(key) for key in required},
        "missing_assumptions": missing,
        "scenarios": {},
        "observed_quote_count": 0,
        "training_eligible": False,
        "caveat": "Model values are estimates, not observed or executable HS5RMP quotes.",
        "market_input_mode": (
            "fixed_hypothetical" if historical_inputs is None else "point_in_time_historical"
        ),
        "historical_input_provenance": (
            None if historical_inputs is None else historical_inputs.get("provenance")
        ),
    }
    rules = assumptions.get("derivative_rules", {})
    if rules.get("partial_fraction") != "0.5":
        missing.append("derivative_rules:partial_fraction=0.5")
    loss_after = rules.get("loss_after_days")
    if (
        type(loss_after) is not int
        or loss_after < 1
        or rules.get("loss_unit") not in {"calendar_days", "trading_sessions"}
        or rules.get("time_rule_status") not in {"reviewed", "hypothetical_interpretation"}
    ):
        missing.append("derivative_rules:conditional_loss_time")
    modeled["missing_assumptions"] = missing
    modeled["status"] = "blocked" if missing else "hypothetical"
    if not missing:
        if product["parameter_status"] != "hypothetical":
            modeled.update(status="blocked", missing_assumptions=["parameter_status:hypothetical"])
        elif product["exercise_style"] != "european_call":
            modeled.update(status="blocked", missing_assumptions=["exercise_style:european_call"])
        else:
            names = ("conservative", "middle", "optimistic")
            scenarios = assumptions.get("scenarios", {})
            missing_scenarios = [name for name in names if name not in scenarios]
            if missing_scenarios:
                modeled.update(status="blocked", missing_assumptions=missing_scenarios)
            else:
                modeled["scenarios"] = {
                    name: _scenario(
                        name,
                        normalized,
                        product,
                        scenarios[name],
                        rules,
                        coverage_reaches_maturity=coverage_reaches_maturity,
                        historical_inputs=historical_inputs,
                    )
                    for name in names
                }
                blocked_count = sum(
                    item["status"] == "blocked_missing_historical_input"
                    for item in modeled["scenarios"].values()
                )
                if blocked_count:
                    modeled["status"] = (
                        "blocked" if blocked_count == len(names) else "partially_blocked"
                    )
                available = {
                    key: value
                    for key, value in modeled["scenarios"].items()
                    if value.get("entry_ask") is not None
                }
                if "middle" in available:
                    modeled["entry_price_sensitivity"] = _entry_sensitivity(
                        normalized[0], product, scenarios["middle"], historical_inputs
                    )
                reference = assumptions.get("reference_prices", {})
                if reference.get("indicative_call_price"):
                    indication = _decimal(reference["indicative_call_price"], positive=True)
                    modeled["indicative_entry_comparison"] = {
                        name: _entry_comparison(value, indication, reference)
                        for name, value in available.items()
                    }
    observed = observed_derivative or {
        "status": "unavailable",
        "return_pct": None,
        "reason": "No authorized historical HS5RMP bid/ask archive supplied.",
        "training_eligible": False,
    }
    return {
        "status": "three_mode_report",
        "format_version": 1,
        "publication_at": publication_at.isoformat(),
        "underlying_data_quality": {
            "bar_count": len(normalized),
            "coverage_start": normalized[0]["date"].isoformat(),
            "coverage_end": normalized[-1]["date"].isoformat(),
            "split_sessions": split_sessions,
            "dividend_sessions": dividend_sessions,
            "dividend_treatment": (
                "events disclosed only; BSM uses each scenario's hypothetical continuous "
                "dividend yield"
            ),
            "excluded_publication_day": publication_at.date().isoformat(),
            "entry_policy": "first complete later session; daily bars have no intraday quotes",
            "maturity_policy": (
                "bars on/after maturity excluded; no last-trading time or settlement invented"
            ),
            "price_scope": "raw underlying OHLC; no derivative substitution",
        },
        "historical_market_input_quality": (
            None if historical_inputs is None else historical_inputs.get("quality")
        ),
        "historical_market_input_provenance": (
            None if historical_inputs is None else historical_inputs.get("provenance")
        ),
        "modes": {
            "OBSERVED_DERIVATIVE": observed,
            "MODELED_DERIVATIVE": modeled,
            "UNDERLYING_SIGNAL": _underlying_signal(normalized, assumptions["underlying_levels"]),
        },
    }
