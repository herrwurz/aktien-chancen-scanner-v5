import hashlib
import json
import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest


def market_batch(
    *,
    asset_id="cik:0000320193",
    cik="0000320193",
    ticker="AAPL",
    sessions=2,
    final_volume=None,
):
    from scanner.market_data.models import InstrumentListing
    from scanner.market_data.providers import normalize_tiingo

    rows = []
    for offset in range(sessions):
        day = date(2025, 1, 2) + timedelta(days=offset)
        volume = final_volume if offset == sessions - 1 and final_volume else 1000 + offset
        rows.append(
            {
                "date": f"{day.isoformat()}T00:00:00Z",
                "open": 100 + offset,
                "high": 102 + offset,
                "low": 99 + offset,
                "close": 101 + offset,
                "volume": volume,
                "adjOpen": 100 + offset,
                "adjHigh": 102 + offset,
                "adjLow": 99 + offset,
                "adjClose": 101 + offset,
                "adjVolume": volume,
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
            "end": (date(2025, 1, 2) + timedelta(days=sessions - 1)).isoformat(),
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
    assert reader.latest_storage_time() == datetime(2026, 10, 25, 9, tzinfo=UTC)
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


def test_raw_usd_turnover_and_raw_risk_scale_survive_adjustment_difference():
    from scanner.opportunities.features import compute_features
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    bars = feature_bars(sessions=250, final_close="110", final_volume="100")
    for row in bars:
        row["raw"] = {
            "open": "200",
            "high": "202",
            "low": "198",
            "close": "200",
            "volume": "50",
        }
    bars[-1]["raw"] = {
        "open": "210",
        "high": "222",
        "low": "208",
        "close": "220",
        "volume": "50",
    }
    for row in bars[-20:]:
        row["adjusted"]["volume"] = "400"
    signal_date = date.fromisoformat(bars[-1]["session_date"])

    features = compute_features(bars, signal_date=signal_date)
    candidate = evaluate_candidate(
        stock_identity(),
        bars,
        as_of=datetime.combine(signal_date, datetime.max.time(), tzinfo=UTC),
        catalysts=[],
        policy=OpportunityPolicy(min_median_dollar_volume=Decimal("1")),
    )

    assert features.median_dollar_volume_20 == Decimal("10000")
    assert features.liquidity_price_basis == "raw_close_x_raw_volume_usd"
    assert candidate.risk.reference_price == Decimal("220")
    assert candidate.risk.reference_price_basis == "raw_session_close"
    assert candidate.risk.feature_price_basis == "adjusted_ohlc"
    assert candidate.risk.raw_per_adjusted_scale == Decimal("2")
    assert candidate.risk.stop_price < Decimal("220") < candidate.risk.target_price


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
            "evidence_status": "issuer_publication",
        },
        {
            "source_id": "news:late",
            "source_type": "SECONDARY",
            "url": "https://news.example/late",
            "title": "Late analyst upgrade",
            "event_type": "analyst_revision",
            "published_at": "2025-09-08T08:00:00+00:00",
            "source_available_at": "2025-09-08T08:01:00+00:00",
            "evidence_status": "source_document",
        },
        {
            "source_id": "community:1",
            "source_type": "COMMUNITY",
            "url": "https://forum.example/post",
            "title": "Rumored partnership",
            "event_type": "partnership",
            "published_at": "2025-09-07T10:00:00+00:00",
            "source_available_at": "2025-09-07T10:01:00+00:00",
            "evidence_status": "discovery_only",
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
    assert candidate.exchange == "NYSE"
    assert candidate.mic == "XNYS"
    assert candidate.score > 0
    assert "volume_spike" in candidate.selection_reasons
    assert candidate.risk.spread_status == "unavailable"
    assert candidate.risk.net_crv is None
    assert candidate.risk.executable is False
    assert candidate.historical_availability_verified is False
    assert candidate.training_eligible is False
    assert "benchmark_unavailable" in candidate.uncertainties
    assert "calendar_unverified" in candidate.uncertainties
    assert candidate.strategy_channels["technical_momentum"].status == "triggered"
    assert candidate.strategy_channels["catalyst_market_confirmation"].status == "inactive"


def test_catalyst_requires_independent_market_confirmation():
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    bars = feature_bars(sessions=250, final_close="100", final_volume="100")
    as_of = datetime.combine(
        date.fromisoformat(bars[-1]["session_date"]), datetime.max.time(), tzinfo=UTC
    )
    catalyst = {
        "source_id": "issuer:contract",
        "source_type": "PRIMARY",
        "url": "https://issuer.example/contract",
        "title": "Contract announcement",
        "event_type": "major_contract",
        "published_at": as_of.isoformat(),
        "source_available_at": as_of.isoformat(),
        "evidence_status": "issuer_publication",
    }

    result = evaluate_candidate(
        stock_identity(),
        bars,
        as_of=as_of,
        catalysts=[catalyst],
        policy=OpportunityPolicy(min_median_dollar_volume=Decimal("1")),
    )

    assert result.status == "watch_only"
    catalyst_channel = result.strategy_channels["catalyst_market_confirmation"]
    assert catalyst_channel.status == "awaiting_confirmation"
    assert result.strategy_channels["technical_momentum"].status == "inactive"


@pytest.mark.parametrize(
    ("identity", "bars", "as_of_delta", "minimum_liquidity", "expected_gate"),
    [
        (stock_identity(instrument_type="fund"), feature_bars(sessions=250), 0, "1", "fund"),
        (
            stock_identity(instrument_type="other"),
            feature_bars(sessions=250),
            0,
            "1",
            "non_operating_company",
        ),
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
    if expected_gate == "insufficient_liquidity":
        assert candidate.features is not None
        assert candidate.risk is None


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
    assert (
        select_catalysts(
            [
                {
                    "source_id": "unknown-proof",
                    "source_type": "PRIMARY",
                    "url": "https://issuer.example/unproved",
                    "title": "Unproved guidance claim",
                    "event_type": "guidance_raise",
                    "published_at": "2025-01-01T10:00:00+00:00",
                    "source_available_at": "2025-01-01T10:01:00+00:00",
                    "evidence_status": "unknown",
                }
            ],
            signal_at=datetime(2025, 1, 1, 12, tzinfo=UTC),
        )
        == []
    )


def test_missing_optional_benchmark_does_not_change_candidate_score():
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    bars = feature_bars(sessions=250, final_volume="20000")
    as_of = datetime.combine(
        date.fromisoformat(bars[-1]["session_date"]), datetime.max.time(), tzinfo=UTC
    )
    policy = OpportunityPolicy(min_median_dollar_volume=Decimal("5000"))
    without = evaluate_candidate(stock_identity(), bars, as_of=as_of, catalysts=[], policy=policy)
    missing = evaluate_candidate(
        stock_identity(),
        bars,
        as_of=as_of,
        catalysts=[],
        benchmark_bars=[],
        policy=policy,
    )

    assert missing.status == without.status == "candidate_research"
    assert missing.score == without.score
    assert missing.features.benchmark_status == "unavailable"

    malformed = feature_bars(sessions=21)
    malformed[-1]["adjusted"]["close"] = None
    invalid = evaluate_candidate(
        stock_identity(),
        bars,
        as_of=as_of,
        catalysts=[],
        benchmark_bars=malformed,
        policy=policy,
    )
    assert invalid.status == without.status
    assert invalid.score == without.score
    assert invalid.features.benchmark_status == "unavailable"


def test_unknown_instrument_type_is_analyzed_but_cannot_become_candidate():
    from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate

    bars = feature_bars(sessions=250, final_volume="20000")
    as_of = datetime.combine(
        date.fromisoformat(bars[-1]["session_date"]), datetime.max.time(), tzinfo=UTC
    )
    result = evaluate_candidate(
        stock_identity(instrument_type="unknown"),
        bars,
        as_of=as_of,
        catalysts=[],
        policy=OpportunityPolicy(min_median_dollar_volume=Decimal("1")),
    )

    assert result.features is not None
    assert result.status == "watch_only"
    assert result.selection_reasons
    assert "instrument_type_unverified" in result.uncertainties


def test_source_bound_instrument_review_can_release_operating_company():
    from scanner.opportunities.report import _reviewed_identity

    identity = stock_identity(instrument_type="unknown")
    as_of = datetime(2026, 10, 25, 12, tzinfo=UTC)
    reviews = {
        "schema_version": "1.0",
        "records": [
            {
                "asset_id": "cik:0000000042",
                "cik": "0000000042",
                "ticker": "EXM",
                "instrument_type": "operating_company",
                "source_url": "https://www.sec.gov/Archives/example.json",
                "source_sha256": "a" * 64,
                "source_retrieved_at": "2026-10-25T09:00:00+00:00",
                "reviewer": "manual-reviewer",
                "reviewed_at": "2026-10-25T10:00:00+00:00",
            }
        ],
    }

    reviewed = _reviewed_identity(identity, "cik:0000000042", reviews, as_of)

    assert reviewed.instrument_type == "operating_company"
    assert reviewed.instrument_type_status == "source_verified"
    assert reviewed.instrument_type_evidence.startswith("https://www.sec.gov/")

    with pytest.raises(ValueError, match="not available"):
        _reviewed_identity(
            identity,
            "cik:0000000042",
            reviews,
            datetime(2026, 10, 25, 8, tzinfo=UTC),
        )


def test_whole_archive_dry_run_is_read_only_complete_and_reproducible(tmp_path):
    from scanner.market_data.archive import MarketDataArchive
    from scanner.news import NewsItem
    from scanner.opportunities.report import run_dry_run, write_report
    from scanner.research import AssetIdentity
    from scanner.research_index.builder import build_index
    from scanner.research_index.repository import ResearchIndex

    available = datetime(2025, 1, 1, tzinfo=UTC)
    assets = [
        AssetIdentity(
            asset_type="stock",
            name="Alpha Corporation",
            ticker="AAA",
            cik="0000000001",
            exchange="NASDAQ",
            mic="XNAS",
            country="US",
            instrument_type="operating_company",
            source_available_at=available,
            retrieved_at=available,
        ),
        AssetIdentity(
            asset_type="stock",
            name="Beta Corporation",
            ticker="BBB",
            cik="0000000002",
            exchange="NASDAQ",
            mic="XNAS",
            country="US",
            instrument_type="operating_company",
            source_available_at=available,
            retrieved_at=available,
        ),
        AssetIdentity(
            asset_type="stock",
            name="Index Fund",
            ticker="FND",
            cik="0000000003",
            exchange="NASDAQ",
            mic="XNAS",
            country="US",
            instrument_type="fund",
            instrument_type_status="source_verified",
            source_available_at=available,
            retrieved_at=available,
        ),
    ]
    news = [
        NewsItem(
            source_id="issuer:alpha",
            source_type="PRIMARY",
            url="https://alpha.example/release",
            title="Alpha raises guidance",
            published_at=datetime(2025, 9, 7, 12, tzinfo=UTC),
            first_seen_at=datetime(2025, 9, 7, 12, 1, tzinfo=UTC),
            retrieved_at=datetime(2025, 9, 7, 12, 1, tzinfo=UTC),
            source_available_at=datetime(2025, 9, 7, 12, 1, tzinfo=UTC),
            company_identifiers={"cik": ["0000000001"]},
            event_type="guidance_raise",
            event_confidence="source_claim",
            evidence_status="issuer_publication",
            license_status="permitted_metadata",
            content_hash="1" * 64,
            origin_id="issuer:alpha",
        ),
        NewsItem(
            source_id="issuer:beta-after-close",
            source_type="PRIMARY",
            url="https://beta.example/release",
            title="Beta raises guidance after close",
            published_at=datetime(2025, 9, 8, 22, tzinfo=UTC),
            first_seen_at=datetime(2025, 9, 8, 22, 1, tzinfo=UTC),
            retrieved_at=datetime(2025, 9, 8, 22, 1, tzinfo=UTC),
            source_available_at=datetime(2025, 9, 8, 22, 1, tzinfo=UTC),
            company_identifiers={"cik": ["0000000002"]},
            event_type="guidance_raise",
            event_confidence="source_claim",
            evidence_status="issuer_publication",
            license_status="permitted_metadata",
            content_hash="2" * 64,
            origin_id="issuer:beta",
        ),
    ]
    index_path = tmp_path / "research.db"
    build_index(index_path, assets=assets, events=[], facts=[], news=news)
    archive_path = tmp_path / "market.sqlite"
    writer = MarketDataArchive(
        archive_path,
        now=lambda: datetime(2026, 10, 25, 9, tzinfo=UTC),
    )
    for number, ticker in enumerate(("AAA", "BBB", "FND"), start=1):
        writer.import_batch(
            market_batch(
                asset_id=f"cik:{number:010d}",
                cik=f"{number:010d}",
                ticker=ticker,
                sessions=250,
                final_volume=50000,
            )
        )

    archive = MarketDataArchive(archive_path, read_only=True)
    pilot_coverage = {
        "status": "partial",
        "selected_count": 4,
        "successful_instruments": 3,
        "archive_sha256": archive.logical_sha256(),
        "coverage_kind": "real_provider_archive",
        "real_provider_coverage_measured": True,
        "requests_attempted": 4,
        "cost_eur": "0",
        "instruments": [
            {"ticker": "AAA", "status": "imported", "session_count": 250},
            {"ticker": "BBB", "status": "imported", "session_count": 250},
            {"ticker": "PXED", "status": "imported", "session_count": 58},
            {"ticker": "VOGX", "status": "provider_data_error", "session_count": 0},
        ],
        "coverage_report_sha256": "c" * 64,
    }
    report = run_dry_run(
        ResearchIndex(index_path),
        archive,
        as_of=datetime(2026, 10, 25, 12, tzinfo=UTC),
        signal_date=date(2025, 9, 8),
        minimum_liquidity=Decimal("1000"),
        pilot_coverage=pilot_coverage,
    )

    assert report["mode"] == "modeled_research"
    assert report["coverage"] == {
        "archive_instruments": 3,
        "research_index_visible_assets": 3,
        "archive_coverage_of_visible_assets": "1",
        "identity_matched": 3,
        "identity_conflicts": 0,
        "candidate_research": 2,
        "watch_only": 0,
        "unavailable": 1,
        "analyzed": 2,
        "gate_reason_counts": {"fund": 1},
    }
    assert report["network_requests"] == 0
    assert report["cost_eur"] == "0"
    assert report["historical_availability_verified"] is False
    assert report["training_eligible"] is False
    assert report["source_pilot"]["status"] == "partial"
    assert report["source_pilot"]["failed_or_incomplete"] == [
        {"session_count": 58, "status": "imported", "ticker": "PXED"},
        {"session_count": 0, "status": "provider_data_error", "ticker": "VOGX"},
    ]
    assert report["coverage"]["analyzed"] == 2
    assert report["top_candidates"][0]["ticker"] == "AAA"
    assert report["top_watchlist"] == []
    assert [row["ticker"] for row in report["results"]] == ["AAA", "BBB", "FND"]
    assert report["results"][0]["exchange"] == "NASDAQ"
    assert report["results"][0]["mic"] == "XNAS"
    assert report["results"][0]["currency"] == "USD"
    assert report["results"][0]["catalysts"][0]["source_type"] == "PRIMARY"
    assert report["results"][1]["catalysts"] == []
    assert report["results"][2]["failed_gates"] == ["fund"]

    stale_report = run_dry_run(
        ResearchIndex(index_path),
        MarketDataArchive(archive_path, read_only=True),
        as_of=datetime(2026, 10, 25, 12, tzinfo=UTC),
        signal_date=date(2025, 9, 18),
        minimum_liquidity=Decimal("1000"),
        pilot_coverage=pilot_coverage,
    )
    assert stale_report["coverage"]["unavailable"] == 3
    assert all("stale_price" in row["failed_gates"] for row in stale_report["results"][:2])

    with pytest.raises(ValueError, match="as_of precedes requested signal date"):
        run_dry_run(
            ResearchIndex(index_path),
            archive,
            as_of=datetime(2025, 9, 7, 12, tzinfo=UTC),
            signal_date=date(2025, 9, 8),
            minimum_liquidity=Decimal("1000"),
        )
    with pytest.raises(ValueError, match="pilot coverage archive mismatch"):
        run_dry_run(
            ResearchIndex(index_path),
            archive,
            as_of=datetime(2026, 10, 25, 12, tzinfo=UTC),
            signal_date=date(2025, 9, 8),
            minimum_liquidity=Decimal("1000"),
            pilot_coverage=pilot_coverage | {"archive_sha256": "0" * 64},
        )
    with pytest.raises(ValueError, match="not measured real-provider"):
        run_dry_run(
            ResearchIndex(index_path),
            archive,
            as_of=datetime(2026, 10, 25, 12, tzinfo=UTC),
            signal_date=date(2025, 9, 8),
            minimum_liquidity=Decimal("1000"),
            pilot_coverage=pilot_coverage
            | {"coverage_kind": "synthetic_fixture", "real_provider_coverage_measured": False},
        )

    repeated = run_dry_run(
        ResearchIndex(index_path),
        MarketDataArchive(archive_path, read_only=True),
        as_of=datetime(2026, 10, 25, 12, tzinfo=UTC),
        signal_date=date(2025, 9, 8),
        minimum_liquidity=Decimal("1000"),
        pilot_coverage=pilot_coverage,
    )
    assert repeated == report
    first = write_report(report, tmp_path / "first")
    second = write_report(repeated, tmp_path / "second")
    assert (tmp_path / "first" / "opportunities.json").read_bytes() == (
        tmp_path / "second" / "opportunities.json"
    ).read_bytes()
    assert (tmp_path / "first" / "opportunities.csv").read_bytes() == (
        tmp_path / "second" / "opportunities.csv"
    ).read_bytes()
    assert first["sha256"] == second["sha256"]
    sidecar = (tmp_path / "first" / "opportunities.sha256").read_text()
    assert "opportunities.json" in sidecar
    assert "opportunities.csv" in sidecar


def test_opportunity_cli_has_no_network_path_and_writes_audited_outputs(
    tmp_path, monkeypatch, capsys
):
    from scanner.opportunities import cli

    calls = {}

    def fake_run(index, archive, **kwargs):
        calls.update(kwargs)
        return {
            "schema_version": "2.5.2",
            "mode": "modeled_research",
            "coverage": {"archive_instruments": 0},
            "results": [],
        }

    monkeypatch.setattr(cli, "run_dry_run", fake_run)
    monkeypatch.setattr(cli, "ResearchIndex", lambda path: ("index", path))
    monkeypatch.setattr(cli, "MarketDataArchive", lambda path, read_only: (path, read_only))
    exit_code = cli.main(
        [
            "--research-index",
            str(tmp_path / "research.db"),
            "--market-archive",
            str(tmp_path / "market.sqlite"),
            "--as-of",
            "2026-10-25T12:00:00+00:00",
            "--signal-date",
            "2025-09-08",
            "--output",
            str(tmp_path / "output"),
        ]
    )

    assert exit_code == 0
    assert calls["signal_date"] == date(2025, 9, 8)
    assert '"mode": "modeled_research"' in capsys.readouterr().out


def test_docker_runner_rejects_overlapping_paths_and_verifies_input_sha(tmp_path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    for name in ("sec-pilot-index.db", "sec-pilot-index.db.manifest.json", "market-data.sqlite"):
        (pilot / name).write_text("fixture")
    coverage = pilot / "coverage.json"
    coverage.write_text(json.dumps({"status": "partial"}))
    digest = hashlib.sha256(coverage.read_bytes()).hexdigest()
    (pilot / "coverage.sha256").write_text(f"{digest}  coverage.json\n")
    script = str(Path(__file__).resolve().parents[1] / "scripts" / "run-opportunity-dry-run.sh")
    environment = os.environ | {
        "PILOT_DIR": str(pilot),
        "VALIDATE_ONLY": "1",
        "SIGNAL_DATE": "2025-12-31",
    }

    overlap = subprocess.run(
        ["bash", script],
        env=environment | {"OUTPUT_DIR": str(pilot / "nested")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert overlap.returncode == 2
    assert "must not overlap" in overlap.stderr
    assert not (pilot / "nested").exists()

    separate = subprocess.run(
        ["bash", script],
        env=environment | {"OUTPUT_DIR": str(tmp_path / "output")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert separate.returncode == 0
    assert "coverage.json: OK" in separate.stdout

    coverage.write_text("tampered")
    tampered = subprocess.run(
        ["bash", script],
        env=environment | {"OUTPUT_DIR": str(tmp_path / "other-output")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert tampered.returncode != 0


def test_cli_rejects_tampered_pilot_coverage_sidecar(tmp_path):
    from scanner.opportunities.cli import _load_pilot_coverage

    path = tmp_path / "coverage.json"
    path.write_text('{"status":"partial"}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".sha256").write_text(f"{digest}  coverage.json\n")
    assert _load_pilot_coverage(str(path))["coverage_report_sha256"] == digest

    path.write_text('{"status":"accepted"}')
    with pytest.raises(ValueError, match="SHA mismatch"):
        _load_pilot_coverage(str(path))


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "not-a-number"])
def test_opportunity_cli_rejects_disabled_or_invalid_liquidity_gate(value):
    from scanner.opportunities import cli

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--research-index",
                "unused.db",
                "--market-archive",
                "unused.sqlite",
                "--as-of",
                "2026-10-25T12:00:00+00:00",
                "--signal-date",
                "2025-09-08",
                "--output",
                "unused",
                "--minimum-liquidity",
                value,
            ]
        )
