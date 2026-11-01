"""Shared coverage accounting regression tests."""

from datetime import UTC, datetime

import pytest

from scanner.stock_monitor.coverage import SourceCoverage, summarize_coverage


def test_unavailable_is_not_no_signal():
    coverage = summarize_coverage(
        [
            SourceCoverage("SEC", "checked", datetime(2026, 11, 1, tzinfo=UTC), "No new filing"),
            SourceCoverage("social", "unavailable", None, "No authenticated source"),
        ]
    )
    assert coverage["complete"] is False
    assert coverage["coverage"]["unavailable"] == 1


def test_reject_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        summarize_coverage([SourceCoverage("SEC", "checked", datetime(2026, 11, 1), "Checked")])


def test_empty_coverage_is_incomplete():
    assert summarize_coverage([])["complete"] is False
