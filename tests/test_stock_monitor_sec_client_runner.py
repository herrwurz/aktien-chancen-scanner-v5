"""SEC client runner refuses unapproved network requests."""

import pytest

from scanner.stock_monitor.sec_client_runner import run_with_sec_client


def test_network_requires_explicit_budget(tmp_path):
    with pytest.raises(ValueError, match="positive request budget"):
        run_with_sec_client(
            cache_root=tmp_path / "cache",
            journal_path=tmp_path / "journal.jsonl",
            targets=[],
            run_id="test",
            code_version="test",
            allow_network=True,
            max_requests=0,
        )


def test_offline_missing_cache_is_partial(tmp_path):
    from scanner.stock_monitor.worker import SecTarget

    result = run_with_sec_client(
        cache_root=tmp_path / "cache",
        journal_path=tmp_path / "journal.jsonl",
        targets=[SecTarget(1234567, "XYZ")],
        run_id="test",
        code_version="test",
    )
    assert result["status"] == "partial"
    assert result["outcomes"][0]["status"] == "unavailable"
    assert result["successful_targets"] == 0
