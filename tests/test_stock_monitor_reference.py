"""Independent reference-set recall tests."""

from datetime import UTC, datetime

from scanner.stock_monitor.reference import ReferenceOpportunity, reference_recall


def test_empty_reference_is_not_perfect_recall():
    result = reference_recall([], set())
    assert result["recall"] is None
    assert result["status"] == "unavailable"


def test_explicit_reference_denominator():
    now = datetime(2026, 11, 1, tzinfo=UTC)
    references = [
        ReferenceOpportunity("stock", "sec:1", "ABC", now, "verified"),
        ReferenceOpportunity("crypto", "pool:1", "XYZ", now, "verified"),
    ]
    result = reference_recall(references, {"stock:sec:1"})
    assert result["reference_count"] == 2
    assert result["missed_count"] == 1
    assert result["recall"] == 0.5
