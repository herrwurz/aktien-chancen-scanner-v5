"""The US-open quote boilerplate narrows the listing venue, not one company."""

from scanner.hebeltrader.detective.us_session_quote import (
    apply_us_session_quote,
    listed_outside_us_session,
    teaser_quotes_from_us_session,
)

NOTICE = (
    "++ Bitte beachten: Aufgrund der geringen Liquidität an den deutschen Börsen "
    "wird das Derivat erst ab Handelsbeginn in den USA um 14:30 Uhr fortlaufend "
    "quotiert. Danke für Ihr Verständnis! ++"
)


def _row(asset_id, name, ticker, score):
    return {
        "asset_id": asset_id,
        "evidence_score": score,
        "hard_contradictions": [],
        "identity": {"name": name, "ticker": ticker},
    }


def test_boilerplate_is_detected_and_a_bare_clock_is_not():
    assert teaser_quotes_from_us_session(NOTICE)
    assert teaser_quotes_from_us_session(
        "Aufgrund der geringen Liquidität wird das Derivat erst ab Handelsbeginn "
        "in den USA um 14:30 Uhr quotiert."
    )
    assert not teaser_quotes_from_us_session("Kursziel im Chart um 14:30 erreicht.")
    assert not teaser_quotes_from_us_session("Der Versorger hebt die Dividende an.")


def test_home_market_suffix_is_outside_the_us_session_adr_is_not():
    assert listed_outside_us_session("IFX.XETRA")
    assert listed_outside_us_session("STMPA.PA")
    assert listed_outside_us_session("8035.TSE")
    assert listed_outside_us_session("005930.KO")
    assert listed_outside_us_session("XETRA:IFX")
    assert not listed_outside_us_session("SNPS")
    assert not listed_outside_us_session("ASML")
    assert not listed_outside_us_session("TSM")
    assert not listed_outside_us_session("BRK-B")
    assert not listed_outside_us_session("BF.B")
    assert not listed_outside_us_session("AAPL.US")
    assert not listed_outside_us_session(None)


def test_home_listing_falls_behind_us_line_without_naming_a_winner():
    ranked = [
        _row("ifx", "Infineon", "IFX.XETRA", 70),
        _row("asml", "ASML", "ASML", 60),
        _row("snps", "Synopsys", "SNPS", 50),
        _row("tsm", "TSMC", "TSM", 40),
    ]
    summary = apply_us_session_quote(ranked, teaser_text=NOTICE)
    assert summary["status"] == "applied"
    assert [row["asset_id"] for row in ranked] == ["asml", "snps", "tsm", "ifx"]
    assert ranked[-1]["evidence_score"] == 34
    assert ranked[-1]["us_session_quote"]["delta"] == -36
    assert "US-Handelsbeginn" in ranked[-1]["counterarguments"][-1]
    assert [row["evidence_score"] for row in ranked[:3]] == [60, 50, 40]
    skipped = apply_us_session_quote(ranked, teaser_text="Keine Börsenzeiten im Teaser.")
    assert skipped["status"] == "skipped_no_us_session_quote"


def test_pool_drops_home_market_tickers_when_the_warrant_waits_for_the_us_open():
    from scanner.hebeltrader.detective.investigation import _pool_assets_for_teaser

    text = (
        "Der heimliche Herrscher über die globale Chipindustrie. "
        + NOTICE
    )
    tickers = {asset["ticker"] for asset in _pool_assets_for_teaser(text)}
    assert tickers
    assert "IFX.XETRA" not in tickers
    assert "STMPA.PA" not in tickers
    assert "8035.TSE" not in tickers
    assert "SNPS" in tickers
    assert "ASML" in tickers
