from datetime import UTC, datetime

from scanner.hebeltrader.detective.clues import extract_atomic_clues
from scanner.hebeltrader.detective.eu_universe import (
    filter_assets_by_clues,
    load_curated_hypothesis_assets,
    load_us_seed_assets,
)
from scanner.hebeltrader.detective.schemas import DetectiveRequest, SourceSpan
from scanner.research import AssetIdentity
from scanner.research_index.identity import stable_asset_id
from tests.hebeltrader.test_detective_hypothesis_benchmark import _service

HEALTH = (
    "Rekordjagd im Gesundheitssektor – dieser Titel gehört ins Depot! "
    "Ein Gesundheitsriese mit prall gefüllter Kasse. "
    "Die Rallye hat begonnen – Wall-Street-Schwergewicht im Ausbruch! "
    "bis zu plus 1.761 Prozent"
)
FINANCE = (
    "zieht ein Finanzschwergewicht still und leise davon: Gewinne im Aufwind. "
    "bis zu plus 1.705 Prozent"
)
RETAIL = (
    "Wachstum ohne Ende – Handels-Gigant vor der Mega-Aufholjagd! "
    "Aufholjagd im Handel! bis zu 1.438 Prozent"
)

GOLD = {
    "health": "cik:0000200406",  # JNJ
    "finance": "cik:0000019617",  # JPM
    "retail": "cik:0000909832",  # COST
}


def test_us_seed_contains_gold_underlyings():
    by_id = {stable_asset_id(asset): asset for asset in load_us_seed_assets()}
    assert GOLD["health"] in by_id
    assert GOLD["finance"] in by_id
    assert GOLD["retail"] in by_id
    assert by_id[GOLD["health"]].ticker == "JNJ"
    assert by_id[GOLD["finance"]].ticker == "JPM"
    assert by_id[GOLD["retail"]].ticker == "COST"


def test_point_in_time_excludes_future_us_listing():
    future = AssetIdentity(
        asset_type="stock",
        name="Future Bank Fixture",
        ticker="FUTB",
        wkn="A3FUTB",
        isin="US46625H1005",  # collide avoided by different object in filter list only
        country="US",
        sector="finance",
        source_id="test-future",
        source_available_at=datetime(2027, 1, 2, 12, tzinfo=UTC),
        retrieved_at=datetime(2027, 1, 2, 12, tzinfo=UTC),
        instrument_type="operating_company",
        instrument_type_status="source_verified",
    )
    # Use a unique ISIN so merge identity differs from JPM.
    future = future.model_copy(update={"isin": "US0000000F01"})
    text = FINANCE
    clues = extract_atomic_clues(text, [SourceSpan(source_id="t", start=0, end=len(text))])
    as_of = datetime(2025, 10, 1, 12, tzinfo=UTC)
    ranked = filter_assets_by_clues([*load_us_seed_assets(), future], clues, as_of=as_of)
    ids = {stable_asset_id(asset) for asset, _score, _reasons in ranked}
    assert stable_asset_id(future) not in ids
    assert GOLD["finance"] in ids


def test_three_real_teasers_hit_gold_underlyings_in_top3():
    service = _service()
    cases = [
        ("health", HEALTH, GOLD["health"]),
        ("finance", FINANCE, GOLD["finance"]),
        ("retail", RETAIL, GOLD["retail"]),
    ]
    for label, text, expected in cases:
        result = service.analyze(
            DetectiveRequest(teaser_text=text, publication_at="2025-10-01T12:00:00+02:00")
        )
        assert result["identification"]["status"] == "hypothesis_top3", label
        assert result["identification"]["selected_wkn"] is None, label
        assert result["identification"]["selected_asset_id"] is None, label
        top_ids = [row["asset_id"] for row in result["candidates"][:3]]
        assert expected in top_ids, (label, top_ids)
        assert result["identification"]["requires_manual_review"] is True
        assert result["automatic_confirmation"] is False


def test_healthcare_exact_sector_outranks_related_pharma_peer():
    result = _service().analyze(
        DetectiveRequest(teaser_text=HEALTH, publication_at="2025-10-01T12:00:00+02:00")
    )
    top_ids = [row["asset_id"] for row in result["candidates"][:3]]
    assert GOLD["health"] in top_ids
    # Exact healthcare peers (JNJ/UNH) should appear before related pharma-only PFE.
    if "cik:0000078003" in top_ids:  # PFE
        assert top_ids.index(GOLD["health"]) < top_ids.index("cik:0000078003")


def test_curated_universe_merges_eu_and_us():
    assets = load_curated_hypothesis_assets()
    ids = {stable_asset_id(asset) for asset in assets}
    assert "isin:DE0005552004" in ids  # DHL from EU seed
    assert GOLD["health"] in ids
