import json
from datetime import date
from pathlib import Path

from scanner.hebeltrader.detective import market_screen as ms
from scanner.hebeltrader.detective.reference_scan import run_scan
from scanner.hebeltrader.detective.structure_screen import load_universe

UP = [100 + i * 0.3 for i in range(300)]
BLIND = Path("docs/examples/blind-202-26-inputs.json")


def test_reference_scan_attaches_market_hypotheses_from_snapshots(tmp_path):
    load_universe.cache_clear()
    universe = [
        {
            "name": "Up Co",
            "sector": "financial services",
            "ticker": "UPC",
            "layer": "x",
            "structure": "oligopoly",
        },
        {
            "name": "Down Co",
            "sector": "financial services",
            "ticker": "DNC",
            "layer": "x",
            "structure": "oligopoly",
        },
    ]
    snaps = ms.export_snapshots(
        universe=universe,
        fetch={"UPC": UP, "DNC": list(reversed(UP))}.get,
        today=date(2026, 10, 30),
    )
    snap_path = tmp_path / "snaps.json"
    snap_path.write_text(json.dumps(snaps), encoding="utf-8")
    inputs = {
        "schema_version": 1,
        "evaluation_class": "development_regression",
        "cases": [
            {
                "case_id": "T-1",
                "headline": "Chart",
                "teaser_text": "Die Aktie hat die 200-Tage-Linie zurückerobert.",
                "publication_date": "2026-10-30",
                "publication_at": None,
            }
        ],
    }
    # Patch load_universe used by market_screen.rank default — pass via snapshots only;
    # rank() uses load_universe() unless universe arg set. Inject by writing temp?
    # Instead monkeypatch load_universe in market_screen.
    import scanner.hebeltrader.detective.market_screen as market_mod

    market_mod.load_universe = lambda: universe
    in_path = tmp_path / "in.json"
    in_path.write_text(json.dumps(inputs), encoding="utf-8")
    frozen = run_scan(in_path, tmp_path / "out", snapshots=snap_path)
    case = frozen["report"]["cases"][0]
    assert case["market_hypothesis_meta"]["status"] == "unverified_chart_universe_suggestions"
    assert case["market_hypotheses"][0]["ticker"] == "UPC"
    assert case["market_hypothesis_meta"]["clues"] == ["above_gd200"]


def test_blind_202_26_can_be_frozen_without_solution(tmp_path):
    frozen = run_scan(BLIND, tmp_path / "blind-out")
    assert frozen["report"]["evaluation_class"] == "prospective_blind"
    case = frozen["report"]["cases"][0]
    assert case["case_id"] == "BLIND-202-26"
    assert case["identification"]["status"] == "not_identified"
    assert case["market_hypothesis_meta"]["status"] == "snapshots_not_provided"
    # No sector word → no structure-screen suggestions from sector lexicon alone.
    assert isinstance(case["offline_hypotheses"], list)
    assert "sha256" in frozen
    # Persist artifact next to docs for operators (test writes only under tmp).
    artifact = tmp_path / "blind-rankings.json"
    artifact.write_text((tmp_path / "blind-out/rankings.json").read_text(encoding="utf-8"))
    assert "BLIND-202-26" in artifact.read_text(encoding="utf-8")
