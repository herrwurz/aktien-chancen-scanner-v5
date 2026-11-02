"""PIT falsification: quarterly results / ATH must already be public at Stand."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from scanner.hebeltrader.detective.earnings_pit import (
    EarningsEvent,
    StaticEarningsLookup,
    apply_earnings_pit,
    assume_session_time,
    parse_earnings_snippets,
    results_known_by,
    teaser_claims_ath,
    teaser_claims_reported_results,
)

VIENNA = ZoneInfo("Europe/Vienna")


def test_teaser_claim_detectors():
    text = "Starke Quartalszahlen, neues Allzeithoch, Finanztechnologie-Riese"
    assert teaser_claims_reported_results(text)
    assert teaser_claims_ath(text)
    assert not teaser_claims_reported_results("Nur ein Chart-Setup")


def test_visa_after_close_not_known_at_morning_stand():
    stand = datetime(2026, 10, 27, 8, 15, tzinfo=VIENNA)
    visa = EarningsEvent(
        report_at=assume_session_time(date(2026, 10, 27), "after_close"),
        session="after_close",
        source="test",
    )
    ma = EarningsEvent(
        report_at=assume_session_time(date(2026, 10, 29), "before_open"),
        session="before_open",
        source="test",
    )
    ndaq = EarningsEvent(
        report_at=assume_session_time(date(2026, 10, 22), "before_open"),
        session="before_open",
        source="test",
    )
    assert results_known_by(visa, stand) is False
    assert results_known_by(ma, stand) is False
    assert results_known_by(ndaq, stand) is True


def test_apply_earnings_pit_demotes_unreported_leaders():
    stand = datetime(2026, 10, 27, 8, 15, tzinfo=VIENNA)
    lookup = StaticEarningsLookup(
        {
            "MA": EarningsEvent(
                report_at=assume_session_time(date(2026, 10, 29), "before_open"),
                session="before_open",
                source="fixture",
            ),
            "V": EarningsEvent(
                report_at=assume_session_time(date(2026, 10, 27), "after_close"),
                session="after_close",
                source="fixture",
            ),
            "NDAQ": EarningsEvent(
                report_at=assume_session_time(date(2026, 10, 22), "before_open"),
                session="before_open",
                source="fixture",
            ),
        }
    )
    ranked = [
        {
            "asset_id": "ma",
            "identity": {"name": "Mastercard", "ticker": "MA"},
            "evidence_score": 17,
            "hard_contradictions": [],
        },
        {
            "asset_id": "v",
            "identity": {"name": "Visa", "ticker": "V"},
            "evidence_score": 16,
            "hard_contradictions": [],
        },
        {
            "asset_id": "ndaq",
            "identity": {"name": "Nasdaq Inc.", "ticker": "NDAQ"},
            "evidence_score": 12,
            "hard_contradictions": [],
        },
    ]
    summary = apply_earnings_pit(
        ranked,
        stand,
        "Starke Quartalszahlen und neues Allzeithoch",
        lookup=lookup,
        ath_bars_fetcher=lambda ticker: _ath_bars(ticker),
    )
    assert summary["status"] == "applied"
    assert ranked[0]["asset_id"] == "ndaq"
    assert ranked[0]["hard_contradictions"] == []
    assert any("noch nicht öffentlich" in c for c in ranked[1]["hard_contradictions"])
    assert any("noch nicht öffentlich" in c for c in ranked[2]["hard_contradictions"])


def _ath_bars(ticker):
    # NDAQ at ATH on last bar; MA/V deep below a prior peak.
    if ticker == "NDAQ":
        return [
            {"date": "2025-01-02", "close": 80.0},
            {"date": "2026-10-26", "close": 104.72},
        ]
    return [
        {"date": "2025-01-02", "close": 700.0},
        {"date": "2026-10-26", "close": 400.0},
    ]


def test_parse_snippets_visa_after_close():
    event = parse_earnings_snippets(
        [
            "Visa reports fiscal fourth-quarter results after the close Tuesday, Oct. 27, 2026",
            "Analysts expect $3.43 a share",
        ],
        around_year=2026,
    )
    assert event is not None
    assert event.session == "after_close"
    assert event.report_at.date().isoformat() == "2026-10-27"


def test_ath_claim_contradicts_drawdown():
    stand = datetime(2026, 10, 27, 8, 15, tzinfo=VIENNA)
    ranked = [
        {
            "asset_id": "pypl",
            "identity": {"name": "PayPal", "ticker": "PYPL"},
            "evidence_score": 10,
            "hard_contradictions": [],
        }
    ]
    apply_earnings_pit(
        ranked,
        stand,
        "neues Allzeithoch beim Finanztechnologie-Riesen",
        lookup=StaticEarningsLookup({}),
        ath_bars_fetcher=lambda ticker: [
            {"date": "2025-01-17", "close": 90.0},
            {"date": "2026-10-26", "close": 55.0},
        ],
    )
    assert ranked[0]["hard_contradictions"]
    assert "Kein Allzeithoch" in ranked[0]["hard_contradictions"][0]
