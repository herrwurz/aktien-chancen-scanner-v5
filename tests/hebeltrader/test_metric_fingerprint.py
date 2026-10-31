"""199/26 lesson: ARR + operating margin + index growth outranks generic fintech peers."""

from scanner.hebeltrader.detective.metric_fingerprint import (
    apply_metric_fingerprints,
    extract_metric_fingerprint,
    fingerprint_rarity_score,
)

NDAQ_EARNINGS = """
Nasdaq Reports Third Quarter 2026 Results
Index business exploded 39 percent. Annualized recurring revenue reached a record
$3.4 billion. Adjusted operating margin was 57 percent.
Financial technology ARR growth remained strong.
"""

LSEG_TEXT = """
London Stock Exchange Group plc Q3 2026 Trading Update
Strong broad-based growth; total income +8.8%. AI solutions adoption continued.
"""

DB1_TEXT = """
Deutsche Boerse Q3 2026 results. Net revenue grew and guidance was raised.
Exchange operator with data and analytics offerings.
"""


def test_extracts_nasdaq_19926_fingerprint():
    fp = extract_metric_fingerprint(NDAQ_EARNINGS)
    assert fp.arr_billions == 3.4
    assert fp.operating_margin_pct == 57.0
    assert fp.segment_growth is not None
    assert "index" in fp.segment_growth[0]
    assert fp.segment_growth[1] == 39.0
    assert fp.components == 3
    assert fingerprint_rarity_score(fp) > fingerprint_rarity_score(
        extract_metric_fingerprint(LSEG_TEXT)
    )


def test_fingerprint_ranks_nasdaq_above_exchange_peers():
    ranked = [
        {
            "asset_id": "lseg",
            "evidence_score": 12,
            "hard_contradictions": [],
        },
        {
            "asset_id": "ndaq",
            "evidence_score": 5,
            "hard_contradictions": [],
        },
        {
            "asset_id": "db1",
            "evidence_score": 5,
            "hard_contradictions": [],
        },
    ]
    docs = {
        "ndaq": [{"text": NDAQ_EARNINGS, "title": "Nasdaq Q3"}],
        "lseg": [{"text": LSEG_TEXT, "title": "LSEG update"}],
        "db1": [{"text": DB1_TEXT, "title": "DB1 results"}],
    }
    summary = apply_metric_fingerprints(ranked, docs)
    assert summary["status"] == "applied"
    assert ranked[0]["asset_id"] == "ndaq"
    assert ranked[0]["metric_fingerprint"]["components"] == 3
    assert ranked[0]["evidence_score"] > ranked[1]["evidence_score"]


def test_clue_specificity_boosts_arr_and_margin_language():
    from scanner.hebeltrader.detective.investigation import clue_specificity

    assert clue_specificity("ARR of 3.4 billion and operating margin") > clue_specificity(
        "kräftiges Wachstum und KI"
    )
