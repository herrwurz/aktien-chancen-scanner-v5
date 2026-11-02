"""SEC receipts are not equivalent to actionable alerts."""

from scanner.stock_monitor.run_quality import audit_monitor_outcomes


def test_receipts_not_counted_as_alerts():
    result = audit_monitor_outcomes(
        {
            "cutoff": "2026-11-01T12:00:00+00:00",
            "outcomes": [
                {"status": "research_only", "event_count": 4, "symbol": "ABC"},
                {"status": "unavailable", "symbol": "XYZ"},
            ],
        }
    )
    assert result["filing_receipts"] == 4
    assert result["outcomes"]["alerted"] == 0
    assert result["source_runs_unavailable"] == 1
    assert result["recall"] is None
