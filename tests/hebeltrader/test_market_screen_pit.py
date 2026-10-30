from datetime import date, timedelta

from scanner.hebeltrader.detective import market_screen as ms
from scanner.hebeltrader.detective.chart_check import closes_through
from scanner.hebeltrader.detective.reference_scan import run_scan

UNIVERSE = [
    {
        "name": "Up Co",
        "sector": "financial services",
        "ticker": "UPC",
        "layer": "x",
        "structure": "oligopoly",
    }
]


def _bars(start, n, step=0.3):
    out = []
    price = 100.0
    day = start
    while len(out) < n:
        if day.weekday() < 5:
            out.append({"date": day.isoformat(), "close": price})
            price += step
        day += timedelta(days=1)
    return out


def test_closes_through_truncates_at_as_of():
    bars = [
        {"date": "2026-01-01", "close": 1},
        {"date": "2026-01-02", "close": 2},
        {"date": "2026-01-03", "close": 3},
    ]
    assert closes_through(bars, "2026-01-02") == [1, 2]


def test_export_pit_builds_per_date_features_without_leakage():
    bars = _bars(date(2025, 1, 1), 300)
    early = bars[250]["date"]
    late = bars[-1]["date"]
    # Spike only after early as_of so early/late features must differ.
    bars[-1]["close"] = bars[-2]["close"] * 2
    payload = ms.export_pit_snapshots(
        [early, late],
        universe=UNIVERSE,
        fetch_bars={"UPC": bars}.get,
        pause_seconds=0,
    )
    assert payload["format"] == ms.PIT_FORMAT
    assert set(payload["by_as_of"]) == {early, late}
    early_last = payload["by_as_of"][early]["snapshots"]["UPC"]["last"]
    late_last = payload["by_as_of"][late]["snapshots"]["UPC"]["last"]
    assert late_last > early_last


def test_resolve_rejects_single_snapshot_after_publication():
    resolved = ms.resolve_case_snapshots(
        {"as_of": "2026-10-30", "snapshots": {"UPC": {"last": 1}}},
        "2026-05-29",
    )
    assert resolved["status"] == "snapshot_as_of_after_publication"
    assert resolved["snapshots"] is None


def test_resolve_empty_pit_bucket_is_insufficient_history():
    resolved = ms.resolve_case_snapshots(
        {
            "format": ms.PIT_FORMAT,
            "by_as_of": {"2026-05-29": {"as_of": "2026-05-29", "snapshots": {}}},
        },
        "2026-05-29",
    )
    assert resolved["status"] == "insufficient_history_at_as_of"


def test_reference_scan_uses_pit_bucket(tmp_path, monkeypatch):
    bars = _bars(date(2025, 1, 1), 300)
    as_of = bars[-1]["date"]
    pit = ms.export_pit_snapshots(
        [as_of], universe=UNIVERSE, fetch_bars={"UPC": bars}.get, pause_seconds=0
    )
    snap_path = tmp_path / "pit.json"
    snap_path.write_text(__import__("json").dumps(pit), encoding="utf-8")
    monkeypatch.setattr(ms, "load_universe", lambda: UNIVERSE)
    inputs = {
        "schema_version": 1,
        "evaluation_class": "development_regression",
        "cases": [
            {
                "case_id": "T-PIT",
                "headline": "Chart",
                "teaser_text": "Die Aktie hat die 200-Tage-Linie zurückerobert.",
                "publication_date": as_of,
                "publication_at": None,
            }
        ],
    }
    in_path = tmp_path / "in.json"
    in_path.write_text(__import__("json").dumps(inputs), encoding="utf-8")
    frozen = run_scan(in_path, tmp_path / "out", snapshots=snap_path)
    meta = frozen["report"]["cases"][0]["market_hypothesis_meta"]
    assert meta["status"] == "unverified_chart_universe_suggestions"
    assert meta["snapshot_as_of"] == as_of
    assert meta["pit_basis"] == "publication_date_eod"
