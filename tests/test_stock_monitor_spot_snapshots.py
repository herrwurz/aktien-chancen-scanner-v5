"""Cross-run price acceleration regression tests."""

from scanner.stock_monitor.spot_snapshots import rank_snapshot


def test_ranks_positive_change_before_24h_order():
    current = {"AUSDT": {"price": "100"}, "BUSDT": {"price": "105"}}
    previous = {"AUSDT": {"price": "100"}, "BUSDT": {"price": "100"}}
    symbols, mode = rank_snapshot(["AUSDT", "BUSDT"], current, previous)
    assert symbols == ["BUSDT", "AUSDT"]
    assert mode == "cross_run_price_change"


def test_no_previous_snapshot_keeps_existing_order():
    symbols, mode = rank_snapshot(["AUSDT", "BUSDT"], {}, None)
    assert symbols == ["AUSDT", "BUSDT"]
    assert mode == "no_previous_snapshot"
