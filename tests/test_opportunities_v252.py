import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest


def market_batch(*, asset_id="cik:0000320193", cik="0000320193", ticker="AAPL"):
    from scanner.market_data.models import InstrumentListing
    from scanner.market_data.providers import normalize_tiingo

    rows = []
    for offset in range(2):
        day = date(2025, 1, 2) + timedelta(days=offset)
        rows.append(
            {
                "date": f"{day.isoformat()}T00:00:00Z",
                "open": 100 + offset,
                "high": 102 + offset,
                "low": 99 + offset,
                "close": 101 + offset,
                "volume": 1000 + offset,
                "adjOpen": 100 + offset,
                "adjHigh": 102 + offset,
                "adjLow": 99 + offset,
                "adjClose": 101 + offset,
                "adjVolume": 1000 + offset,
                "divCash": 0,
                "splitFactor": 1,
            }
        )
    record = {
        "vendor": "Tiingo",
        "request": {
            "dataset": "daily_prices",
            "symbol": ticker,
            "start": "2025-01-02",
            "end": "2025-01-03",
        },
        "payload": rows,
        "retrieved_at": "2026-10-25T08:00:00+00:00",
        "manifest_sha256": hashlib.sha256(f"{ticker}:manifest".encode()).hexdigest(),
        "raw_sha256": hashlib.sha256(f"{ticker}:raw".encode()).hexdigest(),
        "source_reference": f"https://api.tiingo.com/tiingo/daily/{ticker}/prices",
        "license": "https://www.tiingo.com/documentation/general/overview",
    }
    listing = InstrumentListing(
        asset_id=asset_id,
        cik=cik,
        ticker=ticker,
        exchange="NASDAQ",
        mic="XNAS",
        currency="USD",
        timezone="America/New_York",
        provider_symbol=ticker,
    )
    return normalize_tiingo(record, listing)


def test_read_only_archive_does_not_create_missing_database(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        MarketDataArchive(path, read_only=True)

    assert not path.exists()


def test_read_only_archive_lists_canonical_instruments_without_mutation(tmp_path):
    from scanner.market_data.archive import MarketDataArchive

    path = tmp_path / "market.sqlite"
    writer = MarketDataArchive(
        path,
        now=lambda: datetime(2026, 10, 25, 9, tzinfo=UTC),
    )
    writer.import_batch(market_batch())
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()

    reader = MarketDataArchive(path, read_only=True)

    assert reader.list_instruments() == [
        {
            "asset_id": "cik:0000320193",
            "cik": "0000320193",
            "ticker": "AAPL",
            "exchange": "NASDAQ",
            "mic": "XNAS",
            "currency": "USD",
            "timezone": "America/New_York",
            "provider_symbol": "AAPL",
            "isin": None,
        }
    ]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before


def feature_bars(*, final_close="110", final_volume="200"):
    bars = []
    start = date(2025, 1, 1)
    for offset in range(25):
        current = start + timedelta(days=offset)
        close = Decimal("100") if offset < 24 else Decimal(final_close)
        open_ = Decimal("100") if offset < 24 else Decimal("105")
        high = Decimal("101") if offset < 24 else close + 1
        low = Decimal("99") if offset < 24 else Decimal("104")
        volume = Decimal("100") if offset < 24 else Decimal(final_volume)
        bars.append(
            {
                "session_date": current.isoformat(),
                "raw": {
                    "open": str(open_),
                    "high": str(high),
                    "low": str(low),
                    "close": str(close),
                    "volume": str(volume),
                },
                "adjusted": {
                    "open": str(open_),
                    "high": str(high),
                    "low": str(low),
                    "close": str(close),
                    "volume": str(volume),
                },
            }
        )
    return bars


def test_features_use_exact_prior_windows_and_adjusted_values():
    from scanner.opportunities.features import compute_features

    features = compute_features(feature_bars(), signal_date=date(2025, 1, 25))

    assert features.momentum_5 == Decimal("0.1")
    assert features.momentum_10 == Decimal("0.1")
    assert features.momentum_20 == Decimal("0.1")
    assert features.average_volume_prior_20 == Decimal("100")
    assert features.volume_ratio == Decimal("2")
    assert features.median_dollar_volume_20 == Decimal("10000")
    assert features.atr_14 == Decimal(37) / Decimal(14)
    assert features.atr_percent == features.atr_14 / Decimal("110")
    assert features.gap_percent == Decimal("0.05")
    assert features.trend == "up"
    assert features.prior_20_high == Decimal("101")
    assert features.distance_to_prior_20_high == Decimal("110") / Decimal("101") - 1
    assert features.breakout_20 is True
    assert features.relative_strength_20 is None
    assert features.benchmark_status == "unavailable"


def test_future_bar_cannot_change_features_at_signal_date():
    from scanner.opportunities.features import compute_features

    bars = feature_bars()
    expected = compute_features(bars, signal_date=date(2025, 1, 25))
    future = feature_bars(final_close="999", final_volume="9999")[-1]
    future["session_date"] = "2025-01-26"

    actual = compute_features([*bars, future], signal_date=date(2025, 1, 25))

    assert actual == expected


def test_features_fail_closed_for_short_or_incomplete_adjusted_history():
    from scanner.opportunities.features import compute_features

    with pytest.raises(ValueError, match="21 complete sessions"):
        compute_features(feature_bars()[-20:], signal_date=date(2025, 1, 25))

    incomplete = feature_bars()
    incomplete[-1]["adjusted"]["volume"] = None
    with pytest.raises(ValueError, match="adjusted OHLCV"):
        compute_features(incomplete, signal_date=date(2025, 1, 25))


def test_adjusted_history_prevents_false_split_or_dividend_event():
    from scanner.opportunities.features import compute_features

    bars = feature_bars(final_close="50", final_volume="100")
    for row in bars:
        row["adjusted"] = {
            "open": "50",
            "high": "51",
            "low": "49",
            "close": "50",
            "volume": "200",
        }
    features = compute_features(bars, signal_date=date(2025, 1, 25))

    assert features.raw_reference_close == Decimal("50")
    assert features.adjusted_reference_close == Decimal("50")
    assert features.momentum_20 == 0
    assert features.gap_percent == 0
    assert features.volume_ratio == 1
    assert features.breakout_20 is False


def test_relative_strength_uses_same_bounded_twenty_session_window():
    from scanner.opportunities.features import compute_features

    features = compute_features(
        feature_bars(),
        signal_date=date(2025, 1, 25),
        benchmark_bars=feature_bars(final_close="105", final_volume="100"),
    )

    assert features.relative_strength_20 == Decimal("0.05")
    assert features.benchmark_status == "available"
