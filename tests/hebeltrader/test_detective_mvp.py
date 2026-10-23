import base64
import json
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image

from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService


class FakeOcr:
    engine = "synthetic_test_ocr"

    def extract(self, payload, media_type):
        assert payload == b"synthetic-image"
        assert media_type == "image/png"
        return "US-Pharmakonzern Johnson & Johnson WKN 853260 Call HS5RMP"


def request(**values):
    return DetectiveRequest(**values)


def test_text_clues_rank_top_three_with_explanations_and_no_confirmation():
    service = DetectiveService(clock=lambda: datetime(2026, 10, 23, tzinfo=UTC))
    report = service.analyze(
        request(
            teaser_text=(
                "Gesucht ist ein Pharma- und Healthcare-Konzern. Alternativ könnten Merck oder "
                "ein US-Konzern mit Dividende gemeint sein."
            ),
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    assert report["strategy"] == "HEBELTRADER_DETECTIVE"
    assert 1 <= len(report["candidates"]) <= 3
    assert report["candidates"][0]["name"] == "Merck KGaA"
    assert all(candidate["evidence"] for candidate in report["candidates"])
    assert all(candidate["confirmed"] is False for candidate in report["candidates"])
    assert report["identification_is_investment_recommendation"] is False


def test_exact_stock_and_call_wkn_are_ranked_but_product_stays_unverified():
    report = DetectiveService().analyze(
        request(teaser_text="Johnson & Johnson: Aktien-WKN 853260, Call HS5RMP")
    )
    candidate = report["candidates"][0]
    assert candidate["name"] == "Johnson & Johnson"
    assert candidate["confidence"] == "high"
    call = candidate["call_candidates"][0]
    assert call["wkn"] == "HS5RMP"
    assert call["confirmed"] is False
    assert call["ratio"] is None
    assert any("Publication timestamp missing" in hint for hint in report["review_hints"])


def test_screenshot_ocr_is_sha_bound_and_requires_visual_review():
    encoded = base64.b64encode(b"synthetic-image").decode()
    report = DetectiveService(ocr=FakeOcr()).analyze(
        request(screenshot_base64=encoded, screenshot_media_type="image/png")
    )
    assert report["candidates"][0]["wkn"] == "853260"
    assert report["observed_image_sha256"] == (
        "6f252e1d85c9df6308cbb574aa764fcb8d35d477e9cca0adfa6257617f1fffd7"
    )
    assert report["input_sources"][0]["engine"] == "synthetic_test_ocr"
    assert any("visual review" in hint for hint in report["review_hints"])


def test_local_image_validation_rejects_wrong_type_and_accepts_small_png():
    from scanner.hebeltrader.detective.ocr import validate_image

    stream = BytesIO()
    Image.new("RGB", (30, 20), "white").save(stream, format="PNG")
    validate_image(stream.getvalue(), "image/png")
    with pytest.raises(ValueError, match="media type"):
        validate_image(stream.getvalue(), "application/pdf")
    with pytest.raises(ValueError, match="invalid screenshot"):
        validate_image(b"not-an-image", "image/png")


def test_empty_or_malformed_inputs_are_rejected():
    with pytest.raises(ValueError, match="teaser text or screenshot"):
        request()
    with pytest.raises(ValueError, match="media type required"):
        request(screenshot_base64="YQ==")
    with pytest.raises(ValueError, match="invalid screenshot base64"):
        DetectiveService(ocr=FakeOcr()).analyze(
            request(screenshot_base64="%%%", screenshot_media_type="image/png")
        )


def test_offline_cli_writes_reproducible_audit_report(tmp_path):
    from scanner.hebeltrader.detective.cli import main

    source = tmp_path / "teaser.txt"
    source.write_text("Johnson & Johnson WKN 853260 Call HS5RMP")
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--text-file",
                str(source),
                "--publication-at",
                "2025-08-05T08:15:00+02:00",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_bytes())
    assert report["candidates"][0]["ticker"] == "JNJ"
    assert report["candidates"][0]["call_candidates"][0]["confirmed"] is False
