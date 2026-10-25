from datetime import UTC, datetime

from scanner.hebeltrader.detective.index_source import IndexCandidateSource
from scanner.hebeltrader.detective.retrieval import retrieve_candidates
from scanner.hebeltrader.detective.schemas import AtomicClue
from scanner.research import AssetIdentity
from scanner.research_index.models import CandidateBatch, CandidateHit

AS_OF = datetime(2025, 5, 7, 12, tzinfo=UTC)


def clue(category, normalized, *, scope="stock", value=None):
    return AtomicClue(
        clue_id=f"{category}-{normalized}",
        category=category,
        normalized=normalized,
        quote=normalized,
        source_id="teaser",
        start=0,
        end=len(normalized),
        instrument_scope=scope,
        value=value,
    )


def identity(name, cik, *, country="US", sector="pharma", instrument_type="operating_company"):
    return AssetIdentity(
        asset_type="stock",
        name=name,
        ticker=name[:3].upper(),
        cik=cik,
        country=country,
        sector=sector,
        instrument_type=instrument_type,
        instrument_type_status=("source_verified" if instrument_type != "unknown" else "unknown"),
        source_id="sec",
        source_available_at=AS_OF,
        retrieved_at=AS_OF,
    )


class FakeIndex:
    def __init__(self, channel_hits):
        self.channel_hits = channel_hits
        self.queries = []

    def candidates(self, query, *, as_of, limit):
        self.queries.append((query, as_of, limit))
        if query.sectors:
            key = "sector"
        elif query.countries:
            key = "country"
        elif query.event_types or query.fact_claims:
            key = "event"
        else:
            key = "text"
        hits = [
            CandidateHit(
                identity=item,
                score=0,
                confirmed=[],
                contradicted=[],
                unknown=[],
                evidence_source_ids=[],
            )
            for item in self.channel_hits.get(key, [])
        ]
        return CandidateBatch(
            status="ok" if hits else "unresolved",
            candidates=hits[:limit],
            full_universe_size=5000,
            visible_universe_size=4900,
            matched_before_limit=len(hits),
            limit=limit,
            index_payload_sha256="a" * 64,
        )


def test_retrieval_fuses_channels_and_applies_frozen_structural_scores():
    alpha = identity("Alpha", "0000000001")
    beta = identity("Beta", "0000000002", country="DE")
    index = FakeIndex(
        {"sector": [alpha, beta], "country": [beta, alpha], "event": [alpha], "text": []}
    )

    report = retrieve_candidates(
        index,
        [
            clue("sectors", "pharma"),
            clue("countries", "US"),
            clue("events", "guidance_raise"),
        ],
        as_of=AS_OF,
    )

    assert report.status == "ok"
    assert report.full_universe_size == 5000
    assert report.visible_universe_size == 4900
    assert [item.identity.name for item in report.candidates] == ["Alpha", "Beta"]
    assert report.candidates[0].structured_score == 53  # country + sector + event
    assert report.candidates[1].structured_score == -5  # sector, but wrong country
    assert report.candidates[0].channel_ranks == {"country": 2, "event": 1, "sector": 1}
    assert all(limit == 50 for _, _, limit in index.queries)


def test_promotional_only_teaser_is_insufficiently_constrained():
    index = FakeIndex({"text": [identity("Random", "0000000009")]})
    report = retrieve_candidates(
        index,
        [clue("promotional_derivative_return", "return", scope="promotional", value="1091")],
        as_of=AS_OF,
    )
    assert report.status == "insufficiently_constrained"
    assert report.candidates == []
    assert index.queries == []


def test_known_funds_are_excluded_and_unknown_instrument_types_are_retained_with_warning():
    fund = identity("Fund", "0000000010", instrument_type="fund")
    unknown = identity("Unknown", "0000000011", instrument_type="unknown")
    index = FakeIndex({"sector": [fund, unknown]})

    report = retrieve_candidates(index, [clue("sectors", "pharma")], as_of=AS_OF)

    assert [item.identity.name for item in report.candidates] == ["Unknown"]
    assert report.candidates[0].uncertainties == ["instrument_type_unverified"]
    assert report.exclusions[0].reason == "known_non_stock_instrument"


def test_derivative_identifier_never_constrains_stock_retrieval():
    index = FakeIndex({"text": [identity("Wrong", "0000000012")]})
    report = retrieve_candidates(
        index,
        [clue("identifier", "derivative_wkn", scope="derivative", value="HS5RMP")],
        as_of=AS_OF,
    )
    assert report.status == "insufficiently_constrained"
    assert index.queries == []


def test_index_source_exposes_v3_retrieval_and_selected_candidates():
    alpha = identity("Alpha", "0000000013")
    source = IndexCandidateSource(FakeIndex({"sector": [alpha]}))

    report = source.retrieve_candidates([clue("sectors", "pharma")], AS_OF)

    assert report.candidates[0].identity.name == "Alpha"
    assert source.load_candidates()[0]["identity"]["name"] == "Alpha"
    assert source.coverage["visible_universe_size"] == 4900
