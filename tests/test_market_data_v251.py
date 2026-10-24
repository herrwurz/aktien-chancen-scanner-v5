from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError


def listing(**changes):
    from scanner.market_data.models import InstrumentListing

    values = {
        "asset_id": "sec:0000320193",
        "ticker": "AAPL",
        "exchange": "NASDAQ",
        "mic": "XNAS",
        "currency": "USD",
        "timezone": "America/New_York",
        "provider_symbol": "AAPL",
    }
    values.update(changes)
    return InstrumentListing(**values)


def tiingo_record(rows):
    return {
        "vendor": "Tiingo",
        "request": {
            "dataset": "daily_prices",
            "symbol": "AAPL",
            "start": "2025-01-02",
            "end": "2025-01-03",
        },
        "payload": rows,
        "retrieved_at": "2025-01-06T12:00:00+00:00",
        "manifest_sha256": "a" * 64,
        "raw_sha256": "b" * 64,
        "source_reference": "https://api.tiingo.com/tiingo/daily/AAPL/prices",
        "license": "https://www.tiingo.com/documentation/general/overview",
    }


def row(day="2025-01-02", **changes):
    values = {
        "date": f"{day}T00:00:00.000Z",
        "open": 100,
        "high": 110,
        "low": 90,
        "close": 105,
        "volume": 1000,
        "adjOpen": 50,
        "adjHigh": 55,
        "adjLow": 45,
        "adjClose": 52.5,
        "adjVolume": 2000,
        "divCash": 0.25,
        "splitFactor": 2,
    }
    values.update(changes)
    return values


def test_tiingo_normalization_keeps_raw_adjusted_actions_and_quotes_separate():
    from scanner.market_data.providers import normalize_tiingo

    batch = normalize_tiingo(tiingo_record([row()]), listing())

    bar = batch.bars[0]
    assert bar.raw.close == Decimal("105")
    assert bar.adjusted.close == Decimal("52.5")
    assert bar.raw.volume == Decimal("1000")
    assert bar.adjusted.volume == Decimal("2000")
    assert [(action.kind, action.value) for action in batch.actions] == [
        ("dividend", Decimal("0.25")),
        ("split", Decimal("2")),
    ]
    assert batch.quotes == []
    assert batch.quote_availability == "not_provided"
    assert batch.source_status == "raw_archive_integrity_verified"
    assert batch.training_eligible is False


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"mic": "NASDAQ"}, "mic"),
        ({"currency": "usd"}, "currency"),
        ({"timezone": "US/Nowhere"}, "timezone"),
        ({"exchange": "NASDAQ/NYSE"}, "exchange"),
    ],
)
def test_listing_rejects_ambiguous_or_invalid_venue_metadata(change, message):
    with pytest.raises((ValidationError, ValueError), match=message):
        listing(**change)


def test_normalizer_rejects_duplicate_sessions():
    from scanner.market_data.providers import normalize_tiingo

    with pytest.raises(ValueError, match="duplicate session"):
        normalize_tiingo(tiingo_record([row(), row()]), listing())


@pytest.mark.parametrize(
    "change",
    [
        {"low": 101},
        {"high": 104},
        {"volume": -1},
        {"adjLow": 53},
    ],
)
def test_normalizer_rejects_invalid_ohlcv(change):
    from scanner.market_data.providers import normalize_tiingo

    with pytest.raises((ValidationError, ValueError), match="OHLC|volume"):
        normalize_tiingo(tiingo_record([row(**change)]), listing())


def test_normalizer_rejects_provider_identity_mismatch():
    from scanner.market_data.providers import normalize_tiingo

    with pytest.raises(ValueError, match="provider symbol"):
        normalize_tiingo(tiingo_record([row()]), listing(provider_symbol="MSFT"))


def test_eodhd_normalization_does_not_invent_adjusted_prices_or_quotes():
    from scanner.market_data.providers import normalize_eodhd

    record = {
        "vendor": "EODHD",
        "request": {
            "endpoint": "eod",
            "symbol": "AAPL.US",
            "start": "2025-01-02",
            "end": "2025-01-02",
            "delisted": False,
        },
        "payload": [
            {
                "date": "2025-01-02",
                "open": 100,
                "high": 110,
                "low": 90,
                "close": 105,
                "adjusted_close": 104,
                "volume": 1000,
            }
        ],
        "retrieved_at": datetime(2025, 1, 6, 12, tzinfo=UTC).isoformat(),
        "manifest_sha256": "c" * 64,
        "raw_sha256": "d" * 64,
        "source_reference": "https://eodhd.com/api/eod/AAPL.US",
        "license": "https://eodhd.com/terms-conditions",
    }

    batch = normalize_eodhd(record, listing(provider_symbol="AAPL.US"))

    assert batch.bars[0].adjusted.close == Decimal("104")
    assert batch.bars[0].adjusted.open is None
    assert batch.actions == []
    assert batch.quotes == []
    assert batch.bars[0].session_end_at.isoformat() == "2025-01-02T16:00:00-05:00"


def test_contract_preserves_other_corporate_actions_without_invented_value():
    from scanner.market_data.models import CorporateAction

    action = CorporateAction(
        kind="other",
        effective_date="2025-01-02",
        value=None,
        currency=None,
        description="symbol change",
        source_pointer="/actions/0",
    )
    assert action.kind == "other"
    assert action.value is None
