"""Cross-asset runs retain independent coverage and error accounting."""

from datetime import UTC, datetime

from scanner.stock_monitor.cross_asset import run_cross_asset


def test_crypto_failure_does_not_block_stock():
    calls = []

    def stock():
        calls.append("stock")
        return {"status": "complete", "candidate_count": 0}

    def crypto():
        calls.append("crypto")
        raise RuntimeError("provider unavailable")

    result = run_cross_asset(
        run_id="2026-11-01:01",
        stock_scan=stock,
        crypto_scan=crypto,
        now=lambda: datetime(2026, 11, 1, 12, tzinfo=UTC),
    )
    assert calls == ["stock", "crypto"]
    assert result["status"] == "partial"
    assert result["results"]["stock"]["status"] == "complete"
    assert result["results"]["crypto"]["status"] == "unavailable"
    assert result["results"]["crypto"]["error_type"] == "RuntimeError"
    assert result["order_execution"] is False


def test_both_complete():
    result = run_cross_asset(
        run_id="test",
        stock_scan=lambda: {"status": "complete"},
        crypto_scan=lambda: {"status": "complete"},
        now=lambda: datetime(2026, 11, 1, 12, tzinfo=UTC),
    )
    assert result["status"] == "complete"


def test_invalid_scanner_result_does_not_count_as_no_signal():
    result = run_cross_asset(
        run_id="test",
        stock_scan=lambda: {"candidates": []},
        crypto_scan=lambda: {"status": "complete"},
        now=lambda: datetime(2026, 11, 1, 12, tzinfo=UTC),
    )
    assert result["results"]["stock"]["status"] == "unavailable"
