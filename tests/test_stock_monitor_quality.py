"""Quality accounting never invents detection recall."""

from datetime import UTC, datetime

import pytest

from scanner.stock_monitor.quality import CandidateAudit, quality_summary


def test_quality_counts_both_asset_classes_without_claiming_recall():
    items = [
        CandidateAudit(
            "stock", "sec:1", "ABC", datetime(2026, 11, 1, tzinfo=UTC), "alerted", "Filing"
        ),
        CandidateAudit("crypto", "pool:1", "XYZ", None, "missed", "Retrospective discovery"),
    ]
    result = quality_summary(items)
    assert result["outcomes"]["alerted"] == 1
    assert result["outcomes"]["missed"] == 1
    assert result["by_asset"]["crypto"]["missed"] == 1
    assert result["recall"] is None


def test_alert_requires_timestamp():
    with pytest.raises(ValueError, match="timestamp"):
        quality_summary([CandidateAudit("stock", "1", "ABC", None, "alerted", "Unknown")])


def test_duplicate_event_rejected():
    item = CandidateAudit("stock", "1", "ABC", None, "pending", "Pending")
    with pytest.raises(ValueError, match="Duplicate"):
        quality_summary([item, item])
