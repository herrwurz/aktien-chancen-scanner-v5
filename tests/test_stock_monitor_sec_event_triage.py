"""Point-in-time SEC event triage tests."""

from datetime import UTC, datetime

import pytest

from scanner.stock_monitor.sec_event_triage import recent_filing_events


def test_recent_only_and_no_future_leakage():
    record = {
        "retrieved_at": "2026-11-02T08:00:00+00:00",
        "payload": {
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q", "8-K", "4"],
                    "acceptanceDateTime": [
                        "2026-11-02T03:00:00",
                        "2026-10-01T10:00:00",
                        "2026-11-03T10:00:00",
                        "2026-11-02T02:00:00",
                    ],
                    "accessionNumber": [
                        "0000000000-26-000001",
                        "0000000000-26-000002",
                        "0000000000-26-000003",
                        "0000000000-26-000004",
                    ],
                }
            }
        },
    }
    cutoff = datetime(2026, 11, 2, 9, tzinfo=UTC)
    events = recent_filing_events(record, symbol="AAPL", cutoff=cutoff)
    assert len(events) == 1
    assert events[0]["form"] == "8-K"
    assert events[0]["priority"] == "high"
    assert events[0]["classification"] == "filing_type_only_unverified_content"


def test_future_retrieval_rejected():
    recent = dict(form=[], acceptanceDateTime=[], accessionNumber=[])
    record = {
        "retrieved_at": "2026-11-04T08:00:00+00:00",
        "payload": {"filings": {"recent": recent}},
    }
    cutoff = datetime(2026, 11, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="not yet observable"):
        recent_filing_events(record, symbol="AAPL", cutoff=cutoff)
