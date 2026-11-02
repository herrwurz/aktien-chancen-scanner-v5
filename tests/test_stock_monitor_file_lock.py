"""Cross-process journal lock coverage."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from scanner.stock_monitor.cross_asset_journal import append_cross_asset_run, read_run_journal
from scanner.stock_monitor.journal import Decision, Evidence, append_run


def _envelope(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "started_at": "2026-11-02T10:00:00+00:00",
        "completed_at": "2026-11-02T10:00:01+00:00",
        "status": "unavailable",
        "results": {
            "stock": {"status": "unavailable"},
            "crypto": {"status": "unavailable"},
        },
        "order_execution": False,
    }


def test_concurrent_cross_asset_appends_preserve_chain(tmp_path):
    path = tmp_path / "runs.jsonl"

    def write(index: int) -> str:
        return append_cross_asset_run(path, _envelope(f"run-{index}"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        digests = list(pool.map(write, range(20)))
    assert len(digests) == 20
    runs = read_run_journal(path)
    assert len(runs) == 20
    assert {run["run_id"] for run in runs} == {f"run-{i}" for i in range(20)}


def test_stock_journal_lock_allows_serialized_appends(tmp_path):
    path = tmp_path / "journal.jsonl"
    cutoff = datetime(2026, 11, 2, 12, tzinfo=UTC)

    def one(index: int) -> str:
        evidence = Evidence(
            event_id=f"evt-{index}",
            symbol="AAPL",
            source_url="https://www.sec.gov/example",
            source_type="primary",
            published_at=cutoff,
            first_seen_at=cutoff,
            retrieved_at=cutoff,
            content_sha256="a" * 64,
        )
        return append_run(
            path,
            run_id=f"stock-{index}",
            cutoff=cutoff,
            evidence=[evidence],
            decisions=[
                Decision(
                    event_id=evidence.event_id,
                    status="event_detected",
                    reason="lock test",
                    quote_kind="unavailable",
                )
            ],
            code_version="test",
            coverage="lock",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, range(8)))
    assert path.read_text(encoding="utf-8").count("\n") == 8
