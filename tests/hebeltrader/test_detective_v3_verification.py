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

    source_clusters = [
        cluster for cluster in verified.evidence_clusters if cluster.origin_id != "sec"
    ]
    assert len(source_clusters) == 1
    assert source_clusters[0].source_ids == ["issuer-a", "portal-copy"]
    assert verified.excluded_source_ids == ["future", "missing-availability"]


def test_identical_content_with_different_claimed_origins_is_one_cluster():
    asset = identity()
    first = evidence("portal-a", origin="claimed-a", facts={"events": ["guidance_raise"]})
    second = evidence("portal-b", origin="claimed-b", facts={"events": ["guidance_raise"]})
    second = second.model_copy(update={"content_sha256": first.content_sha256})
    verified = verify_candidates(
        report(candidate(asset, 100)),
        [clue("events", "guidance_raise")],
        lambda _: [first, second],
        AS_OF,
    )[0]
    source_clusters = [
        cluster for cluster in verified.evidence_clusters if cluster.origin_id != "sec"
    ]
    assert len(source_clusters) == 1
    assert source_clusters[0].source_ids == ["portal-a", "portal-b"]


def test_near_copy_event_repost_with_different_hash_is_one_cluster():
    asset = identity()
    first = evidence("issuer", origin="issuer", facts={"events": ["guidance_raise"]})
    first = first.model_copy(update={"title": "Alpha raises full year guidance"})
    second = evidence("portal", origin="portal", facts={"events": ["guidance_raise"]})
    second = second.model_copy(update={"title": "Alpha raises full-year guidance today"})
    verified = verify_candidates(
        report(candidate(asset, 100)),
        [clue("events", "guidance_raise")],
        lambda _: [first, second],
        AS_OF,
    )[0]
    non_identity = [cluster for cluster in verified.evidence_clusters if cluster.origin_id != "sec"]
    assert len(non_identity) == 1


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


def test_negated_country_is_contradicted_when_candidate_has_that_country():
    asset = identity()
    negative = clue("countries", "US").model_copy(update={"polarity": "negated"})
    verified = verify_candidates(
        report(candidate(asset, 100)),
        [negative],
        lambda _: [evidence("sec-a", facts={"countries": ["US"]})],
        AS_OF,
    )[0]
    assert verified.evidence_matrix[0].status == "contradicted"
    assert verified.hard_contradictions == ["countries:US"]


def test_high_retrieval_with_hard_contradiction_loses_to_weaker_correct_candidate():
    wrong = identity("WrongCo", "0000000001", country="US")
    right = identity("RightCo", "0000000002", country="DE")
    clues = [
        clue("sectors", "pharma"),
        clue("countries", "DE"),
        clue("events", "guidance_raise"),
    ]

    def loader(asset):
        if asset.cik == wrong.cik:
            return [
                evidence(
                    "wrong-a",
                    kind="issuer",
                    facts={"sectors": ["pharma"], "countries": ["US"]},
                ),
                evidence(
                    "wrong-b",
                    facts={"events": ["guidance_raise"], "sectors": ["pharma"]},
                ),
            ]
        return [
            evidence(
                "right-a",
                kind="issuer",
                facts={"sectors": ["pharma"], "countries": ["DE"]},
            ),
            evidence("right-b", facts={"events": ["guidance_raise"]}),
        ]

    verified = verify_candidates(
        report(candidate(wrong, 200), candidate(right, 40)),
        clues,
        loader,
        AS_OF,
    )

    assert [row.asset_id for row in verified] == [
        f"cik:{right.cik}",
        f"cik:{wrong.cik}",
    ]
    assert verified[0].hard_contradictions == []
    assert verified[1].hard_contradictions == ["countries:DE"]
    assert verified[0].evidence_score > verified[1].evidence_score
    assert verified[0].retrieval_score < verified[1].retrieval_score

    decision = decide(verified, "ok")
    assert decision.status == "likely_candidate"
    assert decision.selected_asset_id == f"cik:{right.cik}"


def test_decide_ignores_hard_contradicted_leader_for_selection():
    contradicted = identity("Wrong", "0000000001", country="US")
    supported = identity("Right", "0000000002", country="DE")
    clues = [
        clue("sectors", "pharma"),
        clue("countries", "DE"),
        clue("events", "guidance_raise"),
    ]
    verified = verify_candidates(
        report(candidate(contradicted, 10), candidate(supported, 10)),
        clues,
        lambda asset: (
            [
                evidence(
                    "wrong",
                    kind="issuer",
                    facts={"sectors": ["pharma"], "countries": ["US"]},
                )
            ]
            if asset.cik == contradicted.cik
            else [
                evidence(
                    "right-a",
                    kind="issuer",
                    facts={"sectors": ["pharma"], "countries": ["DE"]},
                ),
                evidence("right-b", facts={"events": ["guidance_raise"]}),
            ]
        ),
        AS_OF,
    )
    assert verified[0].asset_id.endswith(supported.cik)
    assert decide(verified, "ok").selected_asset_id == f"cik:{supported.cik}"


def test_mismatched_archived_financial_metric_is_hard_contradiction():
    asset = identity()
    metric = AtomicClue(
        clue_id="financial_metric:umsatz",
        category="financial_metric",
        normalized="umsatz",
        quote="Umsatz 18 %",
        source_id="teaser",
        start=0,
        end=10,
        instrument_scope="stock",
        value="18",
        unit="%",
    )
    verified = verify_candidates(
        report(candidate(asset, 10)),
        [metric],
        lambda _: [
            evidence(
                "fact-1",
                facts={"financial_metrics": [{"metric": "umsatz", "value": "5", "unit": "%"}]},
            )
        ],
        AS_OF,
    )[0]
    assert verified.evidence_matrix[0].status == "contradicted"
    assert verified.hard_contradictions == ["financial_metric:umsatz"]
