"""One miss class per resolution, without rewriting the first prediction."""

from datetime import UTC, datetime

from scanner.hebeltrader.detective.case_journal import CaseJournal
from scanner.hebeltrader.detective.history import freeze_analysis
from scanner.hebeltrader.detective.miss_class import classify_miss

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


def _report(candidates, checked=None):
    return {"candidates": candidates, "checked_candidates": checked or candidates}


def test_classes_cover_universe_retrieval_rank_and_contradiction():
    missing = classify_miss(_report([]), resolved_name="Analog Devices")
    assert missing["miss_class"] == "in_universe_not_retrieved"
    assert missing["label"] == "Im Universum, nicht abgerufen"

    unknown = classify_miss(_report([]), resolved_name="Keine Echte Firma GmbH")
    assert unknown["miss_class"] == "not_in_universe"

    misranked = classify_miss(
        _report(
            [
                {"asset_id": "nvda", "identity": {"name": "NVIDIA"}},
                {"asset_id": "adi", "identity": {"name": "Analog Devices"}},
            ]
        ),
        resolved_name="Analog Devices",
        resolved_asset_id="adi",
    )
    assert misranked["miss_class"] == "retrieved_misranked"

    contradicted = classify_miss(
        _report(
            [
                {"asset_id": "nvda", "identity": {"name": "NVIDIA"}},
                {
                    "asset_id": "adi",
                    "identity": {"name": "Analog Devices"},
                    "evidence_matrix": [{"status": "contradicted", "quote": "Bruttomarge"}],
                },
            ]
        ),
        resolved_name="Analog Devices",
        resolved_asset_id="adi",
    )
    assert contradicted["miss_class"] == "contradicted"

    confirmed = classify_miss(
        _report([{"asset_id": "adi", "identity": {"name": "Analog Devices"}}]),
        resolved_name="Analog Devices",
        resolved_asset_id="adi",
    )
    assert confirmed["miss_class"] == "confirmed"


def test_resolution_stores_the_class_and_keeps_the_first_ranking(tmp_path):
    journal = CaseJournal(tmp_path / "journal", clock=lambda: NOW)
    case_id = journal.intake({"teaser_text": "Halbleiter im Hintergrund", "issue": "200/26"})
    path = tmp_path / "frozen.json"
    freeze_analysis(
        {
            "run_id": "ht200",
            "case_id": "ht200",
            "teaser_sha256": "input",
            "identification": {"status": "identified"},
            "candidates": [
                {"asset_id": "nvda", "identity": {"name": "NVIDIA"}},
                {"asset_id": "adi", "identity": {"name": "Analog Devices"}},
            ],
            "countercandidate_count": 5,
            "analysis_seconds": 2,
            "source_quality": {"primary_documents": 1, "documents": 2},
        },
        path,
    )
    journal.record_analysis(case_id, path)
    stored = journal.resolve(
        case_id,
        {
            "asset_id": "adi",
            "name": "Analog Devices",
            "source": "operator",
            "basis": "user",
        },
    )
    assert stored["miss_class"] == "retrieved_misranked"
    state = journal.case(case_id)
    assert state["first_prediction"]["candidates"][0]["asset_id"] == "nvda"
    assert state["miss_class"] == "retrieved_misranked"
    assert state["miss_label"] == "Abgerufen, falsch sortiert"
