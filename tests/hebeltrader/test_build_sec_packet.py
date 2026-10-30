"""Unit checks for SEC packet text focusing (no live EDGAR calls)."""

from scanner.hebeltrader.detective.build_sec_packet import (
    _earnings_name_score,
    _focus_text,
    _pick_needles,
    pick_filings,
    resolve_filing_body,
)


def test_focus_text_prefers_prose_product_token_over_xbrl_member_tag():
    raw = (
        b"<html><body>SKYRIZIMember us-gaap:Something 0001 "
        b"Net revenues for Skyrizi increased 29 percent and Rinvoq sales rose."
        b"</body></html>"
    )
    focused = _focus_text(raw, ("Skyrizi", "Rinvoq"))
    assert "Net revenues for Skyrizi" in focused
    assert "Rinvoq sales" in focused
    # Prose token is kept even when an XBRL *Member tag also contains the letters.
    assert "SKYRIZIMember" in focused or "Skyrizi" in focused


def test_focus_text_prefers_revenue_hit_over_glossary_definition():
    raw = (
        b"<html><body>"
        b"Prevnar family Includes Prevnar 20 and Prevnar 13 for immunization glossary. "
        b"Worldwide revenues for the Prevnar family were $3.3 billion, up 6% operationally."
        b"</body></html>"
    )
    focused = _focus_text(raw, ("Prevnar",))
    assert "$3.3 billion" in focused
    assert "up 6% operationally" in focused


def test_focus_text_keeps_brand_even_when_only_includes_context():
    raw = (
        b"<html><body>"
        b"The Company's portfolio includes industry-leading brands such as "
        b"Carrier, Viessmann, Toshiba, Automated Logic and Carrier Transicold."
        b"</body></html>"
    )
    focused = _focus_text(raw, ("Viessmann", "Toshiba"))
    assert "Viessmann" in focused
    assert "Toshiba" in focused


def test_pick_filings_prefers_earnings_named_6k_when_no_10q():
    rows = [
        {
            "form": "6-K",
            "filed": "2026-10-28",
            "primary": "dp255721_6k.htm",
            "accession": "a",
            "url": "u1",
        },
        {
            "form": "6-K",
            "filed": "2026-10-28",
            "primary": "q32026pr.htm",
            "accession": "b",
            "url": "u2",
        },
        {
            "form": "6-K",
            "filed": "2026-10-22",
            "primary": "notice.htm",
            "accession": "c",
            "url": "u3",
        },
    ]
    picks = pick_filings(rows)
    assert len(picks) == 1
    assert picks[0]["primary"] == "q32026pr.htm"
    assert _earnings_name_score("q32026pr.htm") > _earnings_name_score("dp255721_6k.htm")


def test_pick_filings_still_prefers_10q_over_6k():
    rows = [
        {
            "form": "6-K",
            "filed": "2026-10-28",
            "primary": "q32026earnings.htm",
            "accession": "a",
            "url": "u1",
        },
        {
            "form": "10-Q",
            "filed": "2026-08-06",
            "primary": "jpm-20260630.htm",
            "accession": "b",
            "url": "u2",
        },
    ]
    picks = pick_filings(rows)
    assert picks[0]["form"] == "10-Q"


def test_pick_filings_prefers_6k_over_stale_20f():
    rows = [
        {
            "form": "20-F",
            "filed": "2026-03-12",
            "primary": "db-20251231.htm",
            "accession": "a",
            "url": "u1",
        },
        {
            "form": "6-K",
            "filed": "2026-10-28",
            "primary": "db202610286k.htm",
            "accession": "b",
            "url": "u2",
        },
    ]
    picks = pick_filings(rows)
    assert picks[0]["form"] == "6-K"
    assert picks[0]["filed"] == "2026-10-28"


def test_resolve_filing_body_noop_for_non_6k():
    filing = {
        "form": "10-Q",
        "filed": "2026-08-06",
        "primary": "x.htm",
        "accession": "0001",
        "cik": "19617",
        "url": "https://www.sec.gov/Archives/edgar/data/19617/0001/x.htm",
    }
    assert resolve_filing_body(filing) is filing


def test_pick_needles_drops_generic_finance_tokens():
    assert _pick_needles(("Plenitude", "buyback", "share repurchase", "Castrol")) == (
        "Plenitude",
        "Castrol",
    )
