from datetime import UTC, datetime

from scanner.hebeltrader.detective.catalog import load_products
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService
from tests.hebeltrader.test_detective_hypothesis_benchmark import _service

NOW = datetime(2025, 10, 1, 12, tzinfo=UTC)


def test_explicit_call_wkn_surfaces_unconfirmed_product_linked_to_underlying():
    service = _service()
    # Inject curated call stubs used by the default product catalog.
    service.products = load_products()
    result = service.analyze(
        DetectiveRequest(
            teaser_text=(
                "Wall-Street-Schwergewicht im Gesundheitssektor. "
                "Call-Optionsschein WKN JE11C1 bis zu plus 1.761 Prozent."
            ),
            publication_at=NOW,
        )
    )
    assert result["identification"]["status"] == "hypothesis_top3"
    assert result["identification"]["selected_wkn"] is None
    assert "cik:0000200406" in [row["asset_id"] for row in result["candidates"][:3]]
    derivative = result["derivative_candidate"]
    assert derivative["status"] == "explicit_identifier_with_unverified_product_terms"
    assert derivative["candidates"][0]["wkn"] == "JE11C1"
    assert derivative["candidates"][0]["underlying_wkn"] == "853260"
    assert derivative["candidates"][0]["confirmed"] is False
    assert derivative["candidates"][0]["underlying_matches_stock_candidate"] is True


def test_promo_percent_without_wkn_does_not_invent_call_product():
    result = DetectiveService(
        candidate_source=_service().candidate_source,
        news_source=_service().news_source,
        products=load_products(),
        clock=lambda: NOW,
    ).analyze(
        DetectiveRequest(
            teaser_text="Wall-Street Gesundheitsriese bis zu plus 1.761 Prozent.",
            publication_at=NOW,
        )
    )
    assert result["derivative_candidate"]["status"] == "not_identified"
