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


def feature_bars(*, final_close="110", final_volume="200", sessions=25):
    bars = []
    start = date(2025, 1, 1)
    for offset in range(sessions):
        current = start + timedelta(days=offset)
        final = offset == sessions - 1
        close = Decimal(final_close) if final else Decimal("100")
        open_ = Decimal("105") if final else Decimal("100")
        high = close + 1 if final else Decimal("101")
        low = Decimal("104") if final else Decimal("99")
        volume = Decimal(final_volume) if final else Decimal("100")
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


def stock_identity(*, instrument_type="operating_company"):
    from scanner.research import AssetIdentity

    return AssetIdentity(
        asset_type="stock",
        name="Example Operating Company",
        ticker="EXM",
        cik="0000000042",
        exchange="NYSE",
        mic="XNYS",
        country="US",
        instrument_type=instrument_type,
        instrument_type_status="source_verified",
        source_available_at=datetime(2025, 1, 1, tzinfo=UTC),
        retrieved_at=datetime(2026, 10, 25, tzinfo=UTC),
    )


def test_catalysts_require_point_in_time_evidence_and_preserve_evidence_class():
    from scanner.opportunities.catalysts import select_catalysts

    signal_at = datetime(2025, 9, 7, 23, 59, tzinfo=UTC)
    evidence = [
        {
            "source_id": "issuer:1",
            "source_type": "PRIMARY",
            "url": "https://issuer.example/release",
            "title": "Company raises guidance",
            "event_type": "guidance_raise",
            "published_at": "2025-09-07T12:00:00+00:00",
            "source_available_at": "2025-09-07T12:01:00+00:00",
        },
        {
            "source_id": "news:late",
            "source_type": "SECONDARY",
            "url": "https://news.example/late",
            "title": "Late analyst upgrade",
            "event_type": "analyst_revision",
            "published_at": "2025-09-08T08:00:00+00:00",
            "source_available_at": "2025-09-08T08:01:00+00:00",
        },
        {
            "source_id": "community:1",
            "source_type": "COMMUNITY",
            "url": "https://forum.example/post",
            "title": "Rumored partnership",
            "event_type": "partnership",
            "published_at": "2025-09-07T10:00:00+00:00",
            "source_available_at": "2025-09-07T10:01:00+00:00",
        },
    ]

    catalysts = select_catalysts(evidence, signal_at=signal_at)

    assert [row.source_id for row in catalysts] == ["community:1", "issuer:1"]
    assert catalysts[0].verification_status == "context_only"
    assert catalysts[1].verification_status == "confirmed"


def test_candidate_has_transparent_score_and_non_executable_risk_scenario():
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    bars = feature_bars(sessions=250, final_volume="20000")
    as_of = datetime.combine(
        date.fromisoformat(bars[-1]["session_date"]),
        datetime.max.time(),
        tzinfo=UTC,
    )
    candidate = evaluate_candidate(
        stock_identity(),
        bars,
        as_of=as_of,
        catalysts=[],
        policy=OpportunityPolicy(min_median_dollar_volume=Decimal("5000")),
    )

    assert candidate.status == "candidate_research"
    assert candidate.score > 0
    assert "volume_spike" in candidate.selection_reasons
    assert candidate.risk.spread_status == "unavailable"
    assert candidate.risk.net_crv is None
    assert candidate.risk.executable is False
    assert candidate.historical_availability_verified is False
    assert candidate.training_eligible is False
    assert "benchmark_unavailable" in candidate.uncertainties


@pytest.mark.parametrize(
    ("identity", "bars", "as_of_delta", "minimum_liquidity", "expected_gate"),
    [
        (stock_identity(instrument_type="fund"), feature_bars(sessions=250), 0, "1", "fund"),
        (stock_identity(), feature_bars(sessions=249), 0, "1", "insufficient_sessions"),
        (stock_identity(), feature_bars(sessions=250), 10, "1", "stale_price"),
        (
            stock_identity(),
            feature_bars(sessions=250),
            0,
            "999999999",
            "insufficient_liquidity",
        ),
    ],
)
def test_candidate_hard_gates_fail_closed(
    identity, bars, as_of_delta, minimum_liquidity, expected_gate
):
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    last = date.fromisoformat(bars[-1]["session_date"])
    candidate = evaluate_candidate(
        identity,
        bars,
        as_of=datetime.combine(last + timedelta(days=as_of_delta), datetime.min.time(), UTC),
        catalysts=[],
        policy=OpportunityPolicy(
            min_median_dollar_volume=Decimal(minimum_liquidity),
            max_stale_days=5,
        ),
    )

    assert candidate.status == "unavailable"
    assert expected_gate in candidate.failed_gates


def test_missing_or_late_news_never_creates_a_confirmed_catalyst():
    from scanner.opportunities.catalysts import select_catalysts

    assert select_catalysts([], signal_at=datetime(2025, 1, 1, tzinfo=UTC)) == []
    assert (
        select_catalysts(
            [
                {
                    "source_id": "missing-time",
                    "source_type": "PRIMARY",
                    "url": "https://issuer.example/unknown",
                    "title": "Unproven event",
                    "event_type": "major_contract",
                    "published_at": None,
                    "source_available_at": None,
                }
            ],
            signal_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        == []
    )
