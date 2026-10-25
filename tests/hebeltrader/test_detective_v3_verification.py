from datetime import UTC, datetime, timedelta

from scanner.hebeltrader.detective.retrieval import RetrievalCandidate, RetrievalReport
from scanner.hebeltrader.detective.schemas import AtomicClue
from scanner.hebeltrader.detective.verification import decide, verify_candidates
from scanner.research import AssetIdentity, EvidenceRecord

AS_OF = datetime(2025, 5, 7, 12, tzinfo=UTC)


def identity(name="Alpha", cik="0000000001", **updates):
    values = dict(
        asset_type="stock",
        name=name,
        ticker=name[:3].upper(),
        cik=cik,
        country="US",
        sector="pharma",
        instrument_type="operating_company",
        instrument_type_status="source_verified",
        source_id="sec",
        source_available_at=AS_OF - timedelta(days=100),
        retrieved_at=AS_OF - timedelta(days=100),
    )
    values.update(updates)
    return AssetIdentity(**values)


def clue(category, value):
    return AtomicClue(
        clue_id=f"{category}:{value}",
        category=category,
        normalized=value,
        quote=value,
        source_id="teaser",
        start=0,
        end=len(value),
        instrument_scope="stock",
        value=value,
    )


def evidence(source_id, *, kind="regulatory", origin=None, facts=None, available=AS_OF):
    return EvidenceRecord(
        source_id=source_id,
        url=f"https://example.test/{source_id}",
        title=f"Disclosure {source_id}",
        published_at=available,
        retrieved_at=available,
        effective_at=available,
        source_available_at=available,
        source_kind=kind,
        facts={**(facts or {}), "origin_id": origin or source_id},
        content_sha256=(source_id[-1] * 64),
    )


def report(*rows):
    return RetrievalReport(status="ok", candidates=list(rows), visible_universe_size=100)


def candidate(asset, score):
    return RetrievalCandidate(
        asset_id=f"cik:{asset.cik}",
        identity=asset,
        rrf_score=score,
        structured_score=0,
        total_score=score,
        channel_ranks={"sector": 1},
    )


def test_verification_matrix_distinguishes_confirmed_contradicted_and_unknown():
    asset = identity()
    clues = [clue("sectors", "pharma"), clue("countries", "DE"), clue("products", "robot")]
    records = [evidence("sec-a", facts={"sectors": ["pharma"], "countries": ["US"]})]

    verified = verify_candidates(report(candidate(asset, 100)), clues, lambda _: records, AS_OF)[0]

    assert {cell.clue_id: cell.status for cell in verified.evidence_matrix} == {
        "sectors:pharma": "confirmed",
        "countries:DE": "contradicted",
        "products:robot": "unknown",
    }
    assert verified.hard_contradictions == ["countries:DE"]


def test_reposts_share_one_cluster_and_missing_or_future_availability_is_excluded():
    asset = identity()
    clues = [clue("events", "guidance_raise")]
    records = [
        evidence(
            "issuer-a", kind="issuer", origin="release-1", facts={"events": ["guidance_raise"]}
        ),
        evidence(
            "portal-copy", kind="news", origin="release-1", facts={"events": ["guidance_raise"]}
        ),
        evidence(
            "future",
            facts={"events": ["guidance_raise"]},
            available=AS_OF + timedelta(minutes=1),
        ),
        EvidenceRecord(
            source_id="missing-availability",
            url="https://example.test/missing",
            title="Missing timestamp",
            published_at=AS_OF - timedelta(days=1),
            retrieved_at=AS_OF - timedelta(days=1),
            effective_at=AS_OF - timedelta(days=1),
            source_available_at=None,
            source_kind="news",
            facts={"events": ["guidance_raise"]},
            content_sha256="f" * 64,
        ),
    ]

    verified = verify_candidates(report(candidate(asset, 100)), clues, lambda _: records, AS_OF)[0]

    assert len(verified.evidence_clusters) == 1
    assert verified.evidence_clusters[0].source_ids == ["issuer-a", "portal-copy"]
    assert verified.excluded_source_ids == ["future", "missing-availability"]


def test_decision_uses_frozen_likely_unclear_and_unresolved_thresholds():
    alpha = identity()
    beta = identity("Beta", "0000000002")
    clues = [
        clue("sectors", "pharma"),
        clue("countries", "US"),
        clue("events", "guidance_raise"),
    ]
    evidence_by_cik = {
        alpha.cik: [
            evidence(
                "primary-a",
                kind="issuer",
                facts={"sectors": ["pharma"], "countries": ["US"]},
            ),
            evidence("primary-b", facts={"events": ["guidance_raise"]}),
        ],
        beta.cik: [evidence("beta-a", facts={"sectors": ["pharma"]})],
    }
    verified = verify_candidates(
        report(candidate(alpha, 100), candidate(beta, 70)),
        clues,
        lambda asset: evidence_by_cik[asset.cik],
        AS_OF,
    )

    likely = decide(verified, "ok")
    assert likely.status == "likely_candidate"
    assert likely.selected_asset_id == f"cik:{alpha.cik}"
    assert likely.score_is_probability is False

    close_second = [
        verified[0],
        verified[1].model_copy(update={"evidence_score": verified[0].evidence_score - 10}),
    ]
    assert decide(close_second, "ok").status == "unclear"
    assert decide([], "insufficiently_constrained").status == "unresolved"


def test_missing_publication_time_fails_closed_before_evidence_use():
    asset = identity()
    decision = decide([], "missing_publication_time")
    assert decision.status == "unresolved"
    assert decision.reason == "missing_publication_time"
    assert asset.historically_available_at(AS_OF)
