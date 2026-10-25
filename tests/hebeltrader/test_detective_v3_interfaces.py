import base64
from datetime import UTC, datetime, timedelta
from io import BytesIO

from reportlab.pdfgen import canvas

from scanner.hebeltrader.detective.retrieval import RetrievalCandidate, RetrievalReport
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService
from scanner.research import AssetIdentity, EvidenceRecord

NOW = datetime(2025, 8, 5, 12, tzinfo=UTC)


def pdf_bytes(text):
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.drawString(72, 720, text)
    document.save()
    return buffer.getvalue()


class IndexedSource:
    source_id = "test-index"
    coverage = {"status": "ok", "visible_universe_size": 4949}

    def __init__(self):
        self.identity = AssetIdentity(
            asset_type="stock",
            name="Alpha Pharma",
            ticker="ALP",
            wkn="A1B2C3",
            cik="0000000001",
            country="US",
            sector="pharma",
            instrument_type="operating_company",
            instrument_type_status="source_verified",
            source_id="sec",
            source_available_at=NOW - timedelta(days=100),
            retrieved_at=NOW - timedelta(days=100),
        )

    def retrieve_candidates(self, clues, point_in_time):
        assert point_in_time == NOW
        return RetrievalReport(
            status="ok",
            visible_universe_size=4949,
            candidates=[
                RetrievalCandidate(
                    asset_id="cik:0000000001",
                    identity=self.identity,
                    rrf_score=100,
                    structured_score=53,
                    total_score=100,
                    channel_ranks={"sector": 1, "country": 1, "event": 1},
                )
            ],
        )

    def evidence_for(self, identity):
        common = dict(
            published_at=NOW - timedelta(days=1),
            retrieved_at=NOW - timedelta(days=1),
            effective_at=NOW - timedelta(days=1),
            source_available_at=NOW - timedelta(days=1),
        )
        return [
            EvidenceRecord(
                source_id="issuer-release",
                url="https://issuer.test/release",
                title="Guidance",
                source_kind="issuer",
                facts={
                    "origin_id": "issuer-release",
                    "sectors": ["pharma"],
                    "countries": ["US"],
                },
                content_sha256="a" * 64,
                **common,
            ),
            EvidenceRecord(
                source_id="sec-filing",
                url="https://sec.test/filing",
                title="Filing",
                source_kind="regulatory",
                facts={"origin_id": "sec-filing", "events": ["guidance_raise"]},
                content_sha256="b" * 64,
                **common,
            ),
        ]


def test_indexed_service_returns_v3_top_three_evidence_contract():
    source = IndexedSource()
    service = DetectiveService(candidate_source=source, news_source=source, products=[])
    request = DetectiveRequest(
        teaser_text="US-Konzern aus Pharma, Prognose angehoben", publication_at=NOW
    )

    result = service.analyze(request)

    assert result["schema_version"] == 3
    assert result["identification"]["status"] == "likely_candidate"
    assert result["identification"]["score_is_probability"] is False
    assert result["identification"]["failure_code"] is None
    assert result["candidate_source"]["coverage"]["channel_limit"] == 50
    assert result["candidate_source"]["coverage"]["stage_a_asset_ids"] == ["cik:0000000001"]
    assert result["candidates"][0]["identity"]["ticker"] == "ALP"
    assert {cell["status"] for cell in result["candidates"][0]["evidence_matrix"]} == {"confirmed"}
    assert result["derivative_candidate"]["status"] == "not_identified"


def test_indexed_service_without_publication_time_is_unresolved_and_does_not_research():
    class MustNotRun(IndexedSource):
        def retrieve_candidates(self, clues, point_in_time):
            raise AssertionError("historical retrieval must not run")

    source = MustNotRun()
    result = DetectiveService(candidate_source=source, news_source=source, products=[]).analyze(
        DetectiveRequest(analysis_mode="strict", teaser_text="US-Pharma")
    )
    assert result["identification"]["status"] == "unresolved"
    assert result["identification"]["reason"] == "missing_publication_time"
    assert result["identification"]["failure_code"] == "missing_publication_time"
    assert result["candidates"] == []


def test_pdf_reaches_same_service_pipeline_with_sha_and_page_provenance():
    source = IndexedSource()
    payload = pdf_bytes("US-Konzern aus Pharma, Prognose angehoben")
    result = DetectiveService(candidate_source=source, news_source=source, products=[]).analyze(
        DetectiveRequest(
            pdf_base64=base64.b64encode(payload).decode(),
            pdf_media_type="application/pdf",
            publication_at=NOW,
        )
    )
    assert result["input_sources"][0]["type"] == "pdf"
    assert result["input_sources"][0]["sha256"]
    assert result["input_sources"][0]["pages"][0]["method"] == "pdf_text"
    assert result["candidates"][0]["identity"]["ticker"] == "ALP"


def test_template_uses_dom_text_content_instead_of_html_injection():
    template = open("scanner/templates/detective.html", encoding="utf-8").read()
    assert "innerHTML" not in template
    assert "textContent" in template
    assert "c.identity||c" in template
    assert "failure_code" in template
    assert "hypothesis_top3" in template
    assert "search_queries" in template
    assert "Harte Widersprüche" in template
    assert "Primärbelege" in template
    assert "coverage_warnings" in template
    assert "requires_manual_review" in template
    assert "statusBanner" in template
    assert "Extrahierte Hinweise" in template
    assert "kein einzelner WKN-Gewinner" in template
    assert "innerHTML" not in template
