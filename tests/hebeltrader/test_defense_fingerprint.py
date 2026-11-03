"""HT-204 lesson: RTX-style multi-segment defense beats pure-play primes."""

from scanner.hebeltrader.detective.clues import extract_clues
from scanner.hebeltrader.detective.defense_fingerprint import (
    apply_defense_fingerprints,
    defense_fingerprint_score,
    extract_defense_fingerprint,
    teaser_claims_multi_segment_defense,
    teaser_requires_us_defense,
    teaser_wants_defense_fingerprint,
)
from scanner.hebeltrader.detective.investigation import _apply_us_issuer_hard_filter
from scanner.hebeltrader.detective.research_plan import build_queries

HT204_TEASER = (
    "Auftragsboom ohne Ende: Dieser Rüstungsriese dreht gerade richtig auf!\n"
    "Ein Auftragsboom, explodierende Gewinne und glänzende Wachstumsperspektiven: "
    "Der US-Rüstungsriese läuft auf Hochtouren! Der Konzern vereint gleich mehrere "
    "Weltmarktführer unter einem Dach und punktet mit einer einzigartigen Kombination "
    "aus modernster Militärtechnologie und lukrativen Wartungsverträgen. Der "
    "Auftragsbestand hat einen historischen Rekord erreicht, und das Management hat "
    "die Jahresprognose kräftig angehoben."
)


def test_ht204_teaser_cues_us_multi_segment_defense():
    assert teaser_wants_defense_fingerprint(HT204_TEASER)
    assert teaser_requires_us_defense(HT204_TEASER)
    assert teaser_claims_multi_segment_defense(HT204_TEASER)
    structured = extract_clues(HT204_TEASER)["structured"]
    assert "US" in structured["countries"]
    assert "multi_segment_conglomerate" in structured["events"]
    assert "aftermarket_service" in structured["events"]
    assert "guidance_raise" in structured["events"]


def test_defense_research_queries_target_conglomerate_peers():
    queries = build_queries(HT204_TEASER, [], [])
    blob = " ".join(queries).casefold()
    assert "raytheon" in blob or "collins" in blob or "pratt" in blob
    assert "aftermarket" in blob or "backlog" in blob
    assert "lockheed" in blob or "northrop" in blob


def test_rtx_style_docs_score_above_pure_play_ir():
    rtx_text = (
        "RTX reportable segments include Collins Aerospace, Pratt & Whitney and Raytheon. "
        "Aftermarket sustainment contracts grew; record backlog; raised full-year guidance."
    )
    lmt_text = (
        "Lockheed Martin delivered fighters and missiles. Order backlog remained strong; "
        "no guidance change disclosed in this excerpt."
    )
    rtx = extract_defense_fingerprint(rtx_text)
    lmt = extract_defense_fingerprint(lmt_text)
    assert rtx.multi_segment and rtx.aftermarket and rtx.raised_guidance
    assert not lmt.multi_segment
    assert defense_fingerprint_score(rtx, teaser_text=HT204_TEASER) > defense_fingerprint_score(
        lmt, teaser_text=HT204_TEASER
    )


def test_apply_defense_fingerprints_ranks_rtx_over_lockheed():
    ranked = [
        {
            "asset_id": "lmt",
            "identity": {"name": "Lockheed Martin", "ticker": "LMT", "country": "US"},
            "evidence_score": 56,
            "hard_contradictions": [],
            "counterarguments": [],
        },
        {
            "asset_id": "rtx",
            "identity": {"name": "RTX", "ticker": "RTX", "country": "US"},
            "evidence_score": 46,
            "hard_contradictions": [],
            "counterarguments": [],
        },
        {
            "asset_id": "gd",
            "identity": {"name": "General Dynamics", "ticker": "GD", "country": "US"},
            "evidence_score": 24,
            "hard_contradictions": [],
            "counterarguments": [],
        },
    ]
    docs = {
        "rtx": [
            {
                "title": "RTX 10-Q",
                "source_kind": "regulatory",
                "text": (
                    "Collins Aerospace, Pratt & Whitney and Raytheon segments. "
                    "Aftermarket maintenance contracts; record backlog; raised full-year guidance."
                ),
            }
        ],
        "lmt": [
            {
                "title": "Lockheed 10-Q",
                "source_kind": "regulatory",
                "text": "Fighter and missile programs; backlog remained elevated.",
            }
        ],
        "gd": [
            {
                "title": "GD 10-Q",
                "source_kind": "regulatory",
                "text": "Marine Systems and Combat Systems deliveries continued.",
            }
        ],
    }
    summary = apply_defense_fingerprints(ranked, docs, teaser_text=HT204_TEASER)
    assert summary["status"] == "applied"
    assert ranked[0]["asset_id"] == "rtx"
    assert ranked[0]["evidence_score"] > ranked[1]["evidence_score"]
    assert ranked[1]["defense_fingerprint"]["soft_demote"] > 0


def test_us_defense_hard_filter_demotes_rheinmetall():
    ranked = [
        {
            "identity": {"name": "Rheinmetall", "ticker": "RHM.XETRA", "country": "DE"},
            "evidence_score": 40,
            "hard_contradictions": [],
            "evidence_matrix": [],
            "unknown_clues": [],
            "counterarguments": [],
        },
        {
            "identity": {"name": "RTX", "ticker": "RTX", "country": "US"},
            "evidence_score": 20,
            "hard_contradictions": [],
            "evidence_matrix": [],
            "unknown_clues": [],
            "counterarguments": [],
        },
    ]
    _apply_us_issuer_hard_filter(ranked, HT204_TEASER)
    assert "teaser_requires_us_issuer" in ranked[0]["hard_contradictions"]
    assert ranked[0]["evidence_score"] < 0
    assert ranked[1]["hard_contradictions"] == []
    # Utility demotion must not fire on a defense teaser.
    assert "teaser_requires_utility_issuer" not in ranked[1]["hard_contradictions"]
