from datetime import UTC, datetime

from scanner.hebeltrader.detective.case_journal import CaseJournal
from scanner.hebeltrader.detective.history import freeze_analysis
from scanner.hebeltrader.detective.resolution import draft_error_analysis

NOW = datetime(2026, 11, 3, 10, tzinfo=UTC)


def test_draft_error_analysis_confirms_top_pick():
    report = {
        "candidates": [
            {
                "asset_id": "lmt",
                "identity": {"name": "Lockheed Martin"},
                "supporting_clues": ["Verteidigung"],
                "ranking_reason": "Rüstungsauftrag im Teaser",
            },
            {"asset_id": "rtx", "identity": {"name": "RTX"}},
        ]
    }
    text = draft_error_analysis(report, resolved_name="Lockheed Martin", resolved_asset_id="lmt")
    assert text.startswith("Bestätigung:")
    assert "Lockheed Martin" in text
    assert "Analysebegründung:" in text
    assert "Rang 1:" not in text
    assert "Score" not in text


def test_draft_error_analysis_explains_rank_miss():
    report = {
        "candidates": [
            {
                "asset_id": "wrong",
                "identity": {"name": "Wrong Co"},
                "supporting_clues": ["generischer Hinweis"],
            },
            {
                "asset_id": "right",
                "identity": {"name": "Right Co"},
                "supporting_clues": ["passender Hinweis"],
            },
        ]
    }
    text = draft_error_analysis(report, resolved_name="Right Co", resolved_asset_id="right")
    assert text.startswith("Abweichung:")
    assert "Wrong Co" in text
    assert "Right Co" in text
    assert "Rang 2" in text


def test_resolve_auto_drafts_error_analysis_when_blank(tmp_path):
    journal = CaseJournal(tmp_path / "journal", clock=lambda: NOW)
    case = journal.intake({"teaser_text": "Teaser text", "headline": "Auto draft"})
    journal.begin(case)
    path = tmp_path / "frozen.json"
    freeze_analysis(
        {
            "run_id": "auto",
            "case_id": case,
            "teaser_sha256": "x",
            "identification": {"status": "hypothesis_top3"},
            "candidates": [
                {
                    "asset_id": "top",
                    "identity": {"name": "Top Corp"},
                    "supporting_clues": ["Hinweis A"],
                },
                {"asset_id": "other", "identity": {"name": "Other Corp"}},
            ],
            "countercandidate_count": 2,
            "analysis_seconds": 1,
            "source_quality": {"primary_documents": 1, "documents": 1},
        },
        path,
    )
    journal.record_analysis(case, path)
    result = journal.resolve(
        case,
        {
            "asset_id": "other",
            "name": "Other Corp",
            "source": "Report PDF",
            "basis": "user",
            "error_analysis": "",
        },
    )
    assert result["error_analysis"]
    assert "Abweichung" in result["error_analysis"]
    assert "Top Corp" in result["error_analysis"]
    assert result["correct_rank"] == 2
