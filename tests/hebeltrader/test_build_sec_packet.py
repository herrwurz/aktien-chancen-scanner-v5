"""Unit checks for SEC packet text focusing (no live EDGAR calls)."""

from scanner.hebeltrader.detective.build_sec_packet import _focus_text


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
