"""Offline, point-in-time volatility and ECB FX inputs for derivative research."""

from __future__ import annotations

import csv
import io
import json
import math
import statistics
from bisect import bisect_left
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .eodhd import sha

WINDOWS = (20, 60, 120)


def _decimal(value, *, positive=False):
    try:
        result = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid historical market value") from None
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError("invalid historical market value")
    return result


def _json(path):
    return json.loads(Path(path).read_bytes())


def _price_payload(payload):
    if isinstance(payload, dict) and isinstance(payload.get("bars"), list):
        return payload.get("provider"), payload["bars"]
    if isinstance(payload, list) and all(isinstance(row, dict) for row in payload):
        # adjClose is the provider-specific evidence; the audit file remains the source authority.
        provider = "Tiingo" if all("adjClose" in row for row in payload) else None
        return provider, payload
    raise ValueError("invalid historical price payload")


def _prices(payload):
    provider, rows = _price_payload(payload)
    result = []
    for row in rows:
        day = date.fromisoformat(str(row["date"])[:10])
        value = row.get("adjusted_close", row.get("adjClose"))
        if value is None:
            raise ValueError("adjusted close required for historical volatility")
        result.append((day, _decimal(value, positive=True)))
    return provider, result


def _fx_rows(raw):
    text = raw.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    date_names = ("date", "Date", "Datum", "TIME_PERIOD")
    value_names = ("usd_per_eur", "rate", "USD", "OBS_VALUE")
    result = []
    for row in rows:
        raw_date = next((row.get(key) for key in date_names if row.get(key)), None)
        raw_value = next((row.get(key) for key in value_names if row.get(key)), None)
        if raw_date is None or raw_value is None:
            raise ValueError("ECB CSV requires a date and USD-per-EUR value")
        result.append((date.fromisoformat(raw_date[:10]), _decimal(raw_value, positive=True)))
    if not result:
        raise ValueError("ECB FX series is empty")
    result.sort()
    if len({day for day, _ in result}) != len(result):
        raise ValueError("duplicate ECB fixing date")
    return result


def _volatility(prices, session, window):
    eligible = [(day, value) for day, value in prices if day < session]
    if len(eligible) < window + 1:
        return {"status": "insufficient_history", "required_returns": window}
    selected = eligible[-(window + 1) :]
    returns = [
        math.log(float(current / previous))
        for (_, previous), (_, current) in zip(selected, selected[1:], strict=False)
    ]
    annualized = statistics.stdev(returns) * math.sqrt(252)
    return {
        "status": "available",
        "annualized": format(Decimal(str(annualized)), "f"),
        "annualization_sessions": 252,
        "return_type": "adjusted_close_log_return",
        "observation_count": window,
        "first_price_date": selected[0][0].isoformat(),
        "last_price_date": selected[-1][0].isoformat(),
        "availability_policy": "prices strictly before valuation session",
    }


def load_historical_market_inputs(underlying_path, prehistory_path, fx_path, audit_path):
    """Build dated inputs without modifying or copying any source file."""
    underlying_path, prehistory_path = Path(underlying_path), Path(prehistory_path)
    fx_path, audit_path = Path(fx_path), Path(audit_path)
    current_payload, prior_payload = _json(underlying_path), _json(prehistory_path)
    # Parsing the audit is deliberate: malformed provenance must block the run.
    audit = _json(audit_path)
    if not isinstance(audit, dict):
        raise ValueError("market input audit must be an object")
    current_provider, current_prices = _prices(current_payload)
    prior_provider, prior_prices = _prices(prior_payload)
    if not current_provider or current_provider != prior_provider:
        raise ValueError("underlying provider mismatch")
    prices = sorted(prior_prices + current_prices)
    if len({day for day, _ in prices}) != len(prices):
        raise ValueError("duplicate historical price date")
    fx = _fx_rows(fx_path.read_bytes())
    all_rows = _price_payload(prior_payload)[1] + _price_payload(current_payload)[1]
    gaps = [
        (current[0] - previous[0]).days
        for previous, current in zip(prices, prices[1:], strict=False)
        if (current[0] - previous[0]).days > 4
    ]
    split_events = sum(
        _decimal(row.get("split_factor", row.get("splitFactor", "1")), positive=True) != Decimal(1)
        for row in all_rows
    )
    dividend_events = sum(
        _decimal(row.get("dividend_cash", row.get("divCash", "0"))) != Decimal(0)
        for row in all_rows
    )
    fx_dates = [row[0] for row in fx]
    sessions = {}
    carried = 0
    for session, _ in current_prices:
        position = bisect_left(fx_dates, session) - 1
        if position < 0:
            fx_value = {"status": "unavailable", "reason": "no earlier ECB fixing"}
        else:
            fixing_day, value = fx[position]
            age = (session - fixing_day).days
            carried += age > 1
            fx_value = {
                "usd_per_eur": format(value, "f"),
                "fixing_date": fixing_day.isoformat(),
                "age_calendar_days": age,
                "availability_policy": "latest fixing strictly before session",
            }
        sessions[session.isoformat()] = {
            "fx": fx_value,
            "realized_volatility": {
                str(window): _volatility(prices, session, window) for window in WINDOWS
            },
        }
    return {
        "format_version": 1,
        "status": "historical_market_inputs",
        "provider": current_provider,
        "sessions": sessions,
        "quality": {
            "current_session_count": len(current_prices),
            "prehistory_price_count": len(prior_prices),
            "fx_fixing_count": len(fx),
            "carried_fx_session_count": carried,
            "price_gap_count": len(gaps),
            "max_price_gap_calendar_days": max(gaps, default=0),
            "price_gap_definition": "more than four calendar days between provider sessions",
            "split_event_count": split_events,
            "dividend_event_count": dividend_events,
            "corporate_action_policy": (
                "volatility uses provider adjusted_close; events remain separately disclosed"
            ),
            "volatility_windows": list(WINDOWS),
            "lookahead_policy": "prior adjusted close and strictly earlier ECB fixing",
            "audit_claims_repeated": False,
        },
        "provenance": {
            "underlying_sha256": sha(underlying_path.read_bytes()),
            "prehistory_sha256": sha(prehistory_path.read_bytes()),
            "fx_sha256": sha(fx_path.read_bytes()),
            "audit_sha256": sha(audit_path.read_bytes()),
        },
    }


def audit_batch_readiness(items):
    """Audit future batch inputs without executing a pricing model."""
    results = []
    required = {"underlying", "prehistory", "fx", "audit"}
    for item in items:
        files = item.get("input_files", {})
        missing = sorted(required - {key for key, value in files.items() if value})
        verified = item.get("product_evidence_status") == "verified"
        if missing:
            status = "blocked_missing_market_inputs"
        elif not verified:
            status = "blocked_unverified_product_terms"
        else:
            status = "ready_for_manual_model_authorization"
        results.append(
            {
                "recommendation_id": item.get("recommendation_id"),
                "status": status,
                "missing_input_types": missing,
                "product_evidence_status": item.get("product_evidence_status"),
                "model_executed": False,
            }
        )
    return {
        "status": "batch_readiness_only",
        "item_count": len(results),
        "modeled_count": 0,
        "items": results,
    }
