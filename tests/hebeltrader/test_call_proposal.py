from scanner.hebeltrader.detective.call_proposal import (
    propose_calls,
    score_candidate,
)


def test_disabled_by_default_does_not_score():
    report = {"identification": {"status": "identified"}}
    out = propose_calls(report, [{"wkn": "JY7FDN", "omega": 10.0}])
    assert out["status"] == "disabled"
    assert out["proposals"] == []
    assert out["is_investment_recommendation"] is False


def test_abstains_until_stock_identified():
    out = propose_calls(
        {"identification": {"status": "not_identified"}},
        [{"wkn": "JY7FDN", "omega": 10.0}],
        enabled=True,
    )
    assert out["status"] == "abstain"
    assert out["reason"] == "stock_not_identified"


def test_ranks_publisher_like_call_above_outlier():
    report = {"identification": {"status": "identified"}}
    candidates = [
        {
            "wkn": "OUTLIER",
            "omega": 3.0,
            "labeled_months": 12,
            "strike": 200,
            "spot": 100,
            "warrant_px_eur": 2.5,
            "crv": 5.0,
            "ratio": 1.0,
        },
        {
            "wkn": "JY7FDN",
            "omega": 10.0,
            "labeled_months": 5,
            "strike": 120,
            "spot": 104.72,
            "warrant_px_eur": 0.22,
            "crv": 12.25,
            "ratio": 0.1,
            "issuer": "J.P. Morgan",
        },
    ]
    out = propose_calls(report, candidates, enabled=True, dry_run=True, as_of="2026-10-27")
    assert out["status"] == "dry_run_ranked"
    assert out["proposals"][0]["wkn"] == "JY7FDN"
    assert out["proposals"][0]["score"] > out["proposals"][1]["score"]
    assert out["actual_hebeltrader_call_identified"] is False


def test_score_candidate_prefers_classic_call_band():
    good = score_candidate(
        {
            "omega": 10.1,
            "labeled_months": 5,
            "strike": 150,
            "spot": 130,
            "warrant_px_eur": 0.26,
            "crv": 14.8,
            "ratio": 0.1,
        }
    )
    bad = score_candidate({"instrument": "Knock-Out", "omega": 12.0, "labeled_months": 5})
    assert good["score"] > 50
    assert bad["score"] < 0
