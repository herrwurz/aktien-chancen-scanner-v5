import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from scanner.hebeltrader.detective.benchmark_evaluate import evaluate_rankings
from scanner.hebeltrader.detective.clues import extract_atomic_clues
from scanner.hebeltrader.detective.documents import extract_document
from scanner.hebeltrader.detective.retrieval import retrieve_candidates
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan
from scanner.hebeltrader.detective.verification import decide, verify_candidates
from scanner.research import AssetIdentity, EvidenceRecord
from scanner.research_index.builder import build_index
from scanner.research_index.repository import ResearchIndex

NOW = datetime(2025, 5, 7, 12, tzinfo=UTC)


def asset(**updates):
    values = dict(
        asset_type="stock",
        name="Alpha Pharma",
        ticker="ALP",
        cik="1",
        wkn="A1B2C3",
        isin="US0378331005",
        country="US",
        sector="pharma",
        instrument_type="operating_company",
        instrument_type_status="source_verified",
        retrieved_at=NOW - timedelta(days=1),
        source_available_at=NOW - timedelta(days=1),
    )
    values.update(updates)
    return AssetIdentity(**values)


def pdf_bytes():
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.showPage()
    document.save()
    return buffer.getvalue()


def test_identity_without_proven_availability_is_not_historically_visible(tmp_path):
    unproven = asset(source_available_at=None)
    path = tmp_path / "index.db"
    build_index(path, assets=[unproven], events=[], facts=[], news=[])
    index = ResearchIndex(path)
    assert index.market_universe(as_of=NOW) == []


def test_event_channel_does_not_award_bonus_without_confirmed_event(tmp_path):
    path = tmp_path / "index.db"
    build_index(path, assets=[asset()], events=[], facts=[], news=[])
    clues = extract_atomic_clues(
        "Prognose angehoben",
        [SourceSpan(source_id="teaser", start=0, end=18)],
    )
    result = retrieve_candidates(ResearchIndex(path), clues, as_of=NOW)
    assert result.candidates
    assert result.candidates[0].structured_score == 0
    assert result.candidates[0].rrf_score < 100


def test_browser_naive_publication_time_is_rejected_before_research():
    with pytest.raises(ValueError, match="timezone"):
        DetectiveRequest(teaser_text="US-Pharma", publication_at="2025-05-07T12:00:00")
    aware = DetectiveRequest(teaser_text="US-Pharma", publication_at="2025-05-07T14:00:00+02:00")
    assert aware.publication_at == NOW


def test_empty_ocr_output_is_incomplete():
    class EmptyOcr:
        engine = "empty"

        def extract(self, payload, media_type):
            return ""

    result = extract_document(pdf_bytes(), "application/pdf", ocr=EmptyOcr())
    assert result.complete is False
    assert result.pages[0].status == "failed"
    assert result.pages[0].warnings == ["OCR returned no text"]


@pytest.mark.parametrize("text", ["Aktien-WKN A1B2C3", "ISIN US0378331005"])
def test_exact_stock_identifiers_retrieve_real_index_identity(tmp_path, text):
    path = tmp_path / "index.db"
    build_index(path, assets=[asset()], events=[], facts=[], news=[])
    clues = extract_atomic_clues(text, [SourceSpan(source_id="teaser", start=0, end=len(text))])
    result = retrieve_candidates(ResearchIndex(path), clues, as_of=NOW)
    assert [row.identity.ticker for row in result.candidates] == ["ALP"]


def test_derivative_asset_cannot_enter_stock_reserve(tmp_path):
    path = tmp_path / "index.db"
    build_index(
        path,
        assets=[asset(asset_type="derivative", instrument_type="unknown")],
        events=[],
        facts=[],
        news=[],
    )
    clues = extract_atomic_clues("US-Pharma", [SourceSpan(source_id="teaser", start=0, end=9)])
    result = retrieve_candidates(ResearchIndex(path), clues, as_of=NOW)
    assert result.candidates == []
    assert result.exclusions[0].reason == "known_non_stock_instrument"


def test_all_hard_contradicted_candidates_are_unresolved():
    from scanner.hebeltrader.detective.retrieval import RetrievalCandidate, RetrievalReport

    candidate = RetrievalCandidate(
        asset_id="cik:0000000001",
        identity=asset(),
        rrf_score=10,
        structured_score=0,
        total_score=10,
        channel_ranks={"country": 1},
    )
    text = "Deutsches Pharmaunternehmen"
    clues = extract_atomic_clues(text, [SourceSpan(source_id="teaser", start=0, end=len(text))])
    verified = verify_candidates(
        RetrievalReport(status="ok", candidates=[candidate]), clues, lambda _: [], NOW
    )
    assert verified[0].hard_contradictions
    assert decide(verified, "ok").status == "unresolved"


def test_benchmark_rejects_corrupt_hash_duplicate_cases_and_unreviewed_real_labels(tmp_path):
    rankings = tmp_path / "rankings.json"
    labels = tmp_path / "labels.json"
    row = {
        "case_id": "same",
        "teaser_sha256": "0" * 64,
        "input_text": "Teaser",
        "ranked_asset_ids": ["cik:0000000001"],
        "status": "unresolved",
    }
    rankings.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "corpus_kind": "real_original",
                "ranking_payload_sha256": "f" * 64,
                "cases": [row, row],
            }
        )
    )
    labels.write_text(
        json.dumps(
            {
                "cases": {
                    "same": {
                        "asset_id": "cik:0000000001",
                        "forbidden_identifiers": [],
                    }
                }
            }
        )
    )
    with pytest.raises(ValueError, match="integrity|duplicate|provenance"):
        evaluate_rankings(rankings, labels)


def test_real_runner_mounts_manifest_and_uses_calling_uid():
    script = Path("scripts/run_detective_v3_real.sh").read_text()
    assert "index.db.manifest.json" in script
    assert '--user "$(id -u):$(id -g)"' in script


def test_financial_clue_keeps_period_and_distinguishing_business_terms():
    text = (
        "Der Halbleiterkonzern entwickelt KI-Chips für Rechenzentren. "
        "Der Umsatz stieg im Q2 2025 um 18 %."
    )
    clues = extract_atomic_clues(
        text, [SourceSpan(source_id="teaser", page=2, start=0, end=len(text))]
    )
    metric = next(item for item in clues if item.category == "financial_metric")
    assert metric.period == "Q2 2025"
    assert {item.category for item in clues} >= {"products", "technologies", "business"}


def test_exact_archived_financial_metric_can_be_confirmed():
    from scanner.hebeltrader.detective.retrieval import RetrievalCandidate, RetrievalReport

    text = "Umsatz 18 %"
    metric = next(
        item
        for item in extract_atomic_clues(
            text, [SourceSpan(source_id="teaser", start=0, end=len(text))]
        )
        if item.category == "financial_metric"
    )
    record = EvidenceRecord(
        source_id="fact-1",
        url="https://sec.test/fact-1",
        title="Revenue fact",
        published_at=NOW - timedelta(days=1),
        retrieved_at=NOW - timedelta(days=1),
        effective_at=NOW - timedelta(days=1),
        source_available_at=NOW - timedelta(days=1),
        source_kind="regulatory",
        facts={"financial_metrics": [{"metric": "umsatz", "value": "18", "unit": "%"}]},
        content_sha256="a" * 64,
    )
    candidate = RetrievalCandidate(
        asset_id="cik:0000000001",
        identity=asset(),
        rrf_score=10,
        structured_score=0,
        total_score=10,
        channel_ranks={"event": 1},
    )
    result = verify_candidates(
        RetrievalReport(status="ok", candidates=[candidate]),
        [metric],
        lambda _: [record],
        NOW,
    )[0]
    assert result.evidence_matrix[0].status == "confirmed"
