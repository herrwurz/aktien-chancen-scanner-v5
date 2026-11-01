"""Follow-up windows are not fabricated performance measurements."""

from datetime import UTC, datetime, timedelta

import pytest

from scanner.stock_monitor.followup import Observation, followup_status


def test_followup_due_without_quotes():
    first = datetime(2026, 11, 1, 12, tzinfo=UTC)
    result = followup_status(first, first + timedelta(hours=5))
    assert [item["due"] for item in result["windows"]] == [True, True, False]
    assert all(item["price_return"] is None for item in result["windows"])


def test_future_discovery_rejected():
    first = datetime(2026, 11, 1, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="precedes"):
        followup_status(first, first - timedelta(seconds=1))


def test_observation_rejects_invalid_price():
    first = datetime(2026, 11, 1, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="positive"):
        Observation("XYZ", "sec:123", first, first, 0, "market", "indicative").validate()
