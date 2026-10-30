import base64
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from scanner.hebeltrader.detective.clues import extract_atomic_clues, extract_clues
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService
from scanner.hebeltrader.detective.sources import OfflineFixtureSource


class FakeOcr:
    engine = "synthetic_test_ocr"

    def extract(self, payload, media_type):
        assert payload == b"synthetic-image"
        assert media_type == "image/png"
        return "US-Gesundheitskonzern mit Pharma, Medizintechnik und Dividendenwachstum"


def request(**values):
    return DetectiveRequest(**values)


@pytest.mark.parametrize(
    ("teaser", "expected_status", "expected_top", "expected_top3"),
    [
        (
            "Der gesuchte US-Gesundheitskonzern vereint Pharma und Medizintechnik "
            "und gilt als Dividendenaristokrat.",
            "resolved_candidate",
            "853260",
            {"853260"},
        ),
        (
            "Ein deutscher DAX-Konzern aus der Pharma-Branche steht im Fokus.",
            "unresolved",
            None,
            {"659990"},
        ),
        (
            "Kanadischer Goldminenbetreiber mit neuer Mine und steigender Produktion.",
            "unresolved",
            None,
            set(),
        ),
    ],
)
def test_true_blind_cases_without_solution_identifiers(
    teaser, expected_status, expected_top, expected_top3
):
    report = DetectiveService(clock=lambda: datetime(2026, 10, 23, tzinfo=UTC)).analyze(
        request(teaser_text=teaser, publication_at="2025-08-05T08:15:00+02:00")
    )
    assert not report["extracted_clues"]["stock_wkn"]
    assert not report["extracted_clues"]["isins"]
    assert report["identification"]["status"] == expected_status
    assert report["identification"]["selected_wkn"] == expected_top
    assert {row["wkn"] for row in report["candidates"]} >= expected_top3
    assert report["identification_is_investment_recommendation"] is False


def test_future_evidence_is_excluded_and_can_never_produce_high_confidence():
    candidate = {
        "identity": {
            "asset_type": "stock",
            "name": "Future Pharma",
            "ticker": "FUT",
            "wkn": "A1FUT0",
            "isin": "DE000A1FUT00",
        },
        "aliases": ["future pharma"],
        "evidence": [
            {
                "source_id": "future-news",
                "url": "fixture://future",
                "title": "Future evidence",
                "published_at": "2026-01-01T00:00:00Z",
                "retrieved_at": "2026-01-01T00:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_kind": "fixture",
                "facts": {"sectors": ["pharma"], "countries": ["DE"], "events": []},
                "content_sha256": "a" * 64,
            }
        ],
    }
    source = OfflineFixtureSource([candidate])
    report = DetectiveService(candidate_source=source, products=[]).analyze(
        request(
            teaser_text="Future Pharma, deutscher Pharma-Konzern",
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    item = report["candidates"][0]
    assert item["evidence_strength"] == "insufficient_evidence"
    assert item["eligible_evidence"] == []
    assert item["excluded_future_or_unavailable_source_ids"] == ["future-news"]
    assert report["identification"]["status"] == "unresolved"
    assert report["identification"]["reason"] == "insufficient_evidence"


def test_contradictions_and_ambiguity_are_explicit_and_scores_are_not_probabilities():
    from scanner.hebeltrader.detective.catalog import default_candidate_source

    merck_only = [
        row
        for row in default_candidate_source().load_candidates()
        if row["identity"]["wkn"] == "659990"
    ]
    report = DetectiveService(candidate_source=OfflineFixtureSource(merck_only)).analyze(
        request(
            teaser_text="Deutscher DAX-Konzern aus Pharma, aber keine Laborausrüstung.",
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    merck = next(row for row in report["candidates"] if row["wkn"] == "659990")
    assert merck["evidence_strength"] == "contradicted"
    assert {row["type"] for row in merck["contradictions"]} == {"negated_sectors"}
    assert "relevance_score_not_probability" in merck
    assert report["identification"]["confidence"] == "not_calibrated"


def test_bounded_alias_does_not_match_inside_another_word():
    report = DetectiveService().analyze(
        request(
            teaser_text="Das moderne Design stammt aus Kanada.",
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    deere = next(row for row in report["candidates"] if row["ticker"] == "DE")
    assert not any(fact["type"] == "bounded_name_or_alias" for fact in deere["hard_facts"])


def test_stock_and_derivative_identifiers_are_separate_and_isin_parts_are_not_wkn():
    clues = extract_clues(
        "Aktien-WKN 853260, Call HS5RMP, ISIN US4781601046, beliebige Zahl 123456"
    )
    assert clues["stock_wkn"] == ["853260"]
    assert clues["derivative_wkn"] == ["HS5RMP"]
    assert clues["isins"] == ["US4781601046"]
    assert "478160" not in clues["stock_wkn"]
    assert "123456" not in clues["stock_wkn"]
    invalid = extract_clues("ISIN US4781601047")
    assert invalid["invalid_isins"] == ["US4781601047"]


def test_structured_event_financial_and_date_clues_are_preserved():
    clues = extract_clues(
        "In Q2 2025 wurde die Prognose angehoben; der Umsatz stieg um 12,5 % und "
        "der Cashflow erreichte 3 Mrd. USD."
    )
    assert clues["structured"]["events"] == ["guidance_raise"]
    assert clues["financial_metrics"] == [
        {"metric": "umsatz", "value": "12.5", "unit": "%"},
        {"metric": "cashflow", "value": "3", "unit": "mrd."},
    ]
    assert "Q2 2025" in clues["date_hints"]


def test_gewinnsprung_compound_is_a_financial_metric_clue():
    clues = extract_atomic_clues(
        "Analysten erwarten für 2026 einen Gewinnsprung von mehr als 40 Prozent.",
        [],
    )
    metric = next(c for c in clues if c.category == "financial_metric")
    assert metric.normalized == "gewinn"
    assert metric.value == "40"
    assert metric.period == "2026"


def test_call_finder_requires_explicit_identifier_time_evidence_and_stock_match():
    without_call = DetectiveService().analyze(
        request(
            teaser_text="US-Gesundheitskonzern mit Pharma und Medizintechnik",
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    assert without_call["derivative_candidate"]["status"] == "not_identified"
    assert without_call["derivative_candidate"]["candidates"] == []

    with_call = DetectiveService().analyze(
        request(
            teaser_text=("US-Gesundheitskonzern mit Pharma und Medizintechnik. Call WKN HS5RMP."),
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    product = with_call["derivative_candidate"]["candidates"][0]
    assert product["wkn"] == "HS5RMP"
    assert product["underlying_matches_stock_candidate"] is True
    assert product["confirmed"] is False
    assert product["ratio"] is None


def test_screenshot_ocr_is_sha_bound_and_requires_visual_review():
    encoded = base64.b64encode(b"synthetic-image").decode()
    report = DetectiveService(ocr=FakeOcr()).analyze(
        request(
            screenshot_base64=encoded,
            screenshot_media_type="image/png",
            publication_at="2025-08-05T08:15:00+02:00",
        )
    )
    assert report["identification"]["selected_wkn"] == "853260"
    assert report["observed_image_sha256"] == hashlib.sha256(b"synthetic-image").hexdigest()
    assert report["input_sources"][0]["engine"] == "synthetic_test_ocr"
    assert any("visual review" in hint for hint in report["review_hints"])


def test_local_image_validation_rejects_wrong_type_oversize_and_invalid_image():
    from scanner.hebeltrader.detective.ocr import MAX_IMAGE_BYTES, validate_image

    stream = BytesIO()
    Image.new("RGB", (30, 20), "white").save(stream, format="PNG")
    validate_image(stream.getvalue(), "image/png")
    with pytest.raises(ValueError, match="media type"):
        validate_image(stream.getvalue(), "application/pdf")
    with pytest.raises(ValueError, match="invalid screenshot"):
        validate_image(b"not-an-image", "image/png")
    with pytest.raises(ValueError, match="size"):
        validate_image(b"x" * (MAX_IMAGE_BYTES + 1), "image/png")


def test_empty_or_malformed_inputs_are_rejected():
    with pytest.raises(ValueError, match="teaser text or screenshot"):
        request()
    with pytest.raises(ValueError, match="media type required"):
        request(screenshot_base64="YQ==")
    with pytest.raises(ValueError, match="invalid screenshot base64"):
        DetectiveService(ocr=FakeOcr()).analyze(
            request(screenshot_base64="%%%", screenshot_media_type="image/png")
        )


def test_web_renderer_uses_text_content_and_never_dynamic_inner_html():
    template = Path("scanner/templates/detective.html").read_text()
    assert "innerHTML" not in template
    assert "textContent" in template
    assert "replaceChildren" in template


def test_offline_cli_writes_machine_readable_audit_report(tmp_path):
    from scanner.hebeltrader.detective.cli import main

    source = tmp_path / "teaser.txt"
    source.write_text("US-Gesundheitskonzern mit Pharma, Medizintechnik und Dividendenwachstum")
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
    assert report["identification"]["selected_wkn"] == "853260"
    assert report["candidate_source"]["coverage"]["general_market_coverage"] is False
    assert report["derivative_candidate"]["status"] == "not_identified"
