from datetime import UTC, datetime

from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator

CUT = datetime(2026, 10, 28, 12, tzinfo=UTC)


def document(**extra):
    return {
        "company_name": "Example AG",
        "ticker": "EX",
        "url": "https://issuer.example/release",
        "title": "Release",
        "text": "Example AG acquired AlphaPower and BetaLogic.",
        "source_kind": "issuer",
        "published_at": "2026-10-25T12:00:00+00:00",
        "retrieved_at": "2026-10-28T12:00:00+00:00",
        **extra,
    }


def analyze(tmp_path, docs):
    return Investigator(tmp_path, clock=lambda: CUT).analyze(
        InvestigationRequest(
            teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=CUT
        ),
        documents=docs,
    )


def test_publication_does_not_prove_historical_availability(tmp_path):
    doc = document(retrieved_at="2026-10-29T12:00:00+00:00")
    report = analyze(tmp_path, [doc])
    assert not report["candidates"][0]["confirmed_specific_clues"]
    assert report["source_timing"][0]["availability_status"] == "uncertain"


def test_explicit_late_availability_cannot_be_backdated_to_publication(tmp_path):
    report = analyze(
        tmp_path,
        [
            document(
                source_available_at="2026-10-29T12:00:00+00:00",
                availability_evidence="operator archived provider receipt",
            )
        ],
    )
    assert not report["candidates"][0]["confirmed_specific_clues"]
    assert report["source_timing"][0]["eligibility"] == "after_cutoff"


def test_previously_observed_original_is_available_without_guessing_event_time(tmp_path):
    report = analyze(tmp_path, [document(retrieved_at="2026-10-25T12:05:00+00:00")])
    timing = report["source_timing"][0]
    assert timing["eligibility"] == "eligible"
    assert timing["event_at"] is None
    assert timing["source_available_at"] == "2026-10-25T12:05:00+00:00"


def test_later_revision_is_not_the_original_version(tmp_path):
    report = analyze(
        tmp_path,
        [
            document(
                content_revision_at="2026-10-29T12:00:00+00:00",
                retrieved_at="2026-10-29T12:00:00+00:00",
                source_available_at="2026-10-25T12:00:00+00:00",
                availability_evidence="publication archive",
            )
        ],
    )
    assert not report["candidates"][0]["confirmed_specific_clues"]
    assert report["source_timing"][0]["eligibility"] == "after_cutoff"


def test_naive_or_invalid_source_times_remain_unknown_without_crashing(tmp_path):
    for value in ("2026-10-25T12:00:00", "invalid"):
        report = analyze(tmp_path, [document(published_at=value)])
        assert report["source_timing"][0]["eligibility"] == "uncertain"
        assert not report["candidates"][0]["confirmed_specific_clues"]


def test_later_archive_retrieval_requires_proof_bound_to_same_content(tmp_path):
    doc = document(
        retrieved_at="2026-10-29T12:00:00+00:00",
        source_available_at="2026-10-25T12:00:00+00:00",
        raw_sha256="a" * 64,
        availability_evidence={
            "basis": "archived_snapshot",
            "source_url": "https://archive.example/original",
            "observed_at": "2026-10-25T12:00:00+00:00",
            "content_sha256": "a" * 64,
        },
    )
    request = InvestigationRequest(
        teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=CUT
    )
    report = Investigator(tmp_path).analyze(request, documents=[doc], historical_blind=True)
    assert report["source_timing"][0]["eligibility"] == "eligible"
    assert len(report["candidates"][0]["confirmed_specific_clues"]) == 2
    doc["availability_evidence"]["content_sha256"] = "b" * 64
    report = Investigator(tmp_path).analyze(request, documents=[doc], historical_blind=True)
    assert report["source_timing"][0]["eligibility"] == "uncertain"
    assert not report["candidates"]


def test_sec_edgar_filing_date_binds_late_retrieval_to_filing_availability(tmp_path):
    doc = document(
        url="https://www.sec.gov/Archives/edgar/data/1/0000000001/filing.htm",
        source_kind="regulator",
        published_at="2026-10-25T16:00:00+00:00",
        retrieved_at="2026-10-30T20:00:00+00:00",
        source_available_at="2026-10-25T16:00:00+00:00",
        raw_sha256="c" * 64,
        availability_evidence={
            "basis": "sec_edgar_filing_date",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1/0000000001/filing.htm",
            "observed_at": "2026-10-30T20:00:00+00:00",
            "content_sha256": "c" * 64,
        },
    )
    request = InvestigationRequest(
        teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=CUT
    )
    report = Investigator(tmp_path).analyze(request, documents=[doc], historical_blind=True)
    timing = report["source_timing"][0]
    assert timing["eligibility"] == "eligible"
    assert timing["availability_basis"] == "sec_edgar_filing_date_binding"
    assert timing["source_available_at"] == "2026-10-25T16:00:00+00:00"
    assert len(report["candidates"][0]["confirmed_specific_clues"]) == 2
    doc["availability_evidence"]["source_url"] = "https://example.com/not-edgar"
    report = Investigator(tmp_path).analyze(request, documents=[doc], historical_blind=True)
    assert report["source_timing"][0]["eligibility"] == "uncertain"
    assert not report["candidates"]


def test_sec_edgar_filing_after_cutoff_remains_ineligible(tmp_path):
    doc = document(
        url="https://www.sec.gov/Archives/edgar/data/1/0000000001/filing.htm",
        source_kind="regulator",
        published_at="2026-10-29T16:00:00+00:00",
        retrieved_at="2026-10-30T20:00:00+00:00",
        source_available_at="2026-10-29T16:00:00+00:00",
        raw_sha256="d" * 64,
        availability_evidence={
            "basis": "sec_edgar_filing_date",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1/0000000001/filing.htm",
            "observed_at": "2026-10-30T20:00:00+00:00",
            "content_sha256": "d" * 64,
        },
    )
    request = InvestigationRequest(
        teaser_text="Übernahmen von AlphaPower und BetaLogic.", publication_at=CUT
    )
    report = Investigator(tmp_path).analyze(request, documents=[doc], historical_blind=True)
    assert report["source_timing"][0]["eligibility"] == "after_cutoff"
    assert not report["candidates"]
