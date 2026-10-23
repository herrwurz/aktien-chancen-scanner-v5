import csv
import json
import math
import statistics
from datetime import date, timedelta


def _payload(start, count, *, provider="Tiingo", base=100):
    bars = []
    day = start
    for index in range(count):
        value = base * math.exp((0.01 if index % 2 else -0.005) * index)
        bars.append(
            {
                "date": day.isoformat(),
                "open": str(value),
                "high": str(value * 1.01),
                "low": str(value * 0.99),
                "close": str(value),
                "adjusted_close": str(value),
                "dividend_cash": "0",
                "split_factor": "1",
            }
        )
        day += timedelta(days=1)
    return {"provider": provider, "bars": bars}


def _files(tmp_path, *, prior_count=125, current_count=3, provider="Tiingo"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    prior = _payload(date(2025, 1, 1), prior_count, provider=provider)
    current = _payload(date(2025, 8, 5), current_count, base=170)
    underlying_path = tmp_path / "current.json"
    prehistory_path = tmp_path / "prior.json"
    fx_path = tmp_path / "fx.csv"
    audit_path = tmp_path / "audit.json"
    underlying_path.write_text(json.dumps(current))
    prehistory_path.write_text(json.dumps(prior))
    with fx_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["date", "usd_per_eur"])
        writer.writeheader()
        writer.writerows(
            [
                {"date": "2025-08-04", "usd_per_eur": "1.1500"},
                {"date": "2025-08-05", "usd_per_eur": "1.1546"},
                {"date": "2025-08-07", "usd_per_eur": "1.1600"},
            ]
        )
    audit_path.write_text(json.dumps({"source": "synthetic fixture", "verified": False}))
    return underlying_path, prehistory_path, fx_path, audit_path


def test_point_in_time_volatility_uses_only_closes_before_session(tmp_path):
    from scanner.hebeltrader.historical_inputs import load_historical_market_inputs

    paths = _files(tmp_path)
    result = load_historical_market_inputs(*paths)
    session = result["sessions"]["2025-08-06"]
    all_bars = json.loads(paths[1].read_text())["bars"] + json.loads(paths[0].read_text())["bars"]
    prices = [float(row["adjusted_close"]) for row in all_bars if row["date"] < "2025-08-06"]
    returns = [math.log(b / a) for a, b in zip(prices[-21:-1], prices[-20:], strict=False)]
    expected = statistics.stdev(returns) * math.sqrt(252)
    assert abs(float(session["realized_volatility"]["20"]["annualized"]) - expected) < 1e-12
    assert session["realized_volatility"]["20"]["last_price_date"] == "2025-08-05"
    assert session["realized_volatility"]["20"]["observation_count"] == 20


def test_fx_uses_latest_strictly_earlier_fixing_and_discloses_age(tmp_path):
    from scanner.hebeltrader.historical_inputs import load_historical_market_inputs

    result = load_historical_market_inputs(*_files(tmp_path))
    august_5 = result["sessions"]["2025-08-05"]["fx"]
    august_6 = result["sessions"]["2025-08-06"]["fx"]
    assert august_5 == {
        "usd_per_eur": "1.1500",
        "fixing_date": "2025-08-04",
        "age_calendar_days": 1,
        "availability_policy": "latest fixing strictly before session",
    }
    assert august_6["usd_per_eur"] == "1.1546"
    assert august_6["fixing_date"] == "2025-08-05"
    assert result["quality"]["carried_fx_session_count"] >= 1


def test_missing_long_window_is_explicit_and_files_are_sha_bound(tmp_path):
    from scanner.hebeltrader.historical_inputs import load_historical_market_inputs

    result = load_historical_market_inputs(*_files(tmp_path, prior_count=25))
    volatility = result["sessions"]["2025-08-06"]["realized_volatility"]
    assert volatility["20"]["status"] == "available"
    assert volatility["60"] == {"status": "insufficient_history", "required_returns": 60}
    assert volatility["120"] == {"status": "insufficient_history", "required_returns": 120}
    assert set(result["provenance"]) == {
        "underlying_sha256",
        "prehistory_sha256",
        "fx_sha256",
        "audit_sha256",
    }
    assert all(len(value) == 64 for value in result["provenance"].values())


def test_provider_mismatch_and_duplicate_dates_are_rejected(tmp_path):
    from scanner.hebeltrader.historical_inputs import load_historical_market_inputs

    paths = _files(tmp_path, provider="Other")
    try:
        load_historical_market_inputs(*paths)
    except ValueError as exc:
        assert str(exc) == "underlying provider mismatch"
    else:
        raise AssertionError("provider mismatch accepted")

    paths = _files(tmp_path / "duplicate")
    prehistory = json.loads(paths[1].read_text())
    prehistory["bars"].append(dict(prehistory["bars"][-1]))
    paths[1].write_text(json.dumps(prehistory))
    try:
        load_historical_market_inputs(*paths)
    except ValueError as exc:
        assert str(exc) == "duplicate historical price date"
    else:
        raise AssertionError("duplicate date accepted")
