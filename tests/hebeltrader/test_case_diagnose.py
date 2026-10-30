import json
from datetime import date

from scanner.hebeltrader.detective import market_screen as ms
from scanner.hebeltrader.detective.case_diagnose import (
    diagnose_frozen,
    diagnose_inputs,
    render_markdown,
)
from scanner.hebeltrader.detective.reference_scan import run_scan

UP = [100 + i * 0.3 for i in range(300)]


def test_diagnose_inputs_reports_clues_and_market_top(tmp_path, monkeypatch):
    universe = [
        {
            "name": "Up Co",
            "sector": "financial services",
            "ticker": "UPC",
            "layer": "x",
            "structure": "oligopoly",
        }
    ]
    snaps = ms.export_snapshots(universe=universe, fetch={"UPC": UP}.get, today=date(2026, 10, 30))
    snap_path = tmp_path / "snaps.json"
    snap_path.write_text(json.dumps(snaps), encoding="utf-8")
    inputs = {
        "schema_version": 1,
        "evaluation_class": "development_regression",
        "cases": [
            {
                "case_id": "T-1",
                "headline": "Bank",
                "teaser_text": "Die Aktie hat die 200-Tage-Linie zurückerobert.",
                "publication_date": "2026-10-30",
                "publication_at": None,
            }
        ],
    }
    in_path = tmp_path / "in.json"
    in_path.write_text(json.dumps(inputs), encoding="utf-8")
    monkeypatch.setattr(ms, "load_universe", lambda: universe)
    import scanner.hebeltrader.detective.structure_screen as structure_mod

    monkeypatch.setattr(structure_mod, "load_universe", lambda: universe)
    diagnosis = diagnose_inputs(in_path, snap_path)
    case = diagnosis["cases"][0]
    assert case["chart_clues"] == ["above_gd200"]
    assert case["market_hypotheses"][0]["ticker"] == "UPC"
    assert "Unverified" in case["interpretation"]
    md = render_markdown(diagnosis)
    assert "T-1" in md and "Market Top-8" in md


def test_diagnose_frozen_from_rankings(tmp_path):
    inputs = {
        "schema_version": 1,
        "evaluation_class": "prospective_blind",
        "cases": [
            {
                "case_id": "BLIND-X",
                "headline": "Teaser",
                "teaser_text": "Kein Branchenwort.",
                "publication_date": "2026-10-30",
                "publication_at": None,
            }
        ],
    }
    in_path = tmp_path / "in.json"
    in_path.write_text(json.dumps(inputs), encoding="utf-8")
    frozen = run_scan(in_path, tmp_path / "out")
    diagnosis = diagnose_frozen(tmp_path / "out/rankings.json")
    assert diagnosis["ranking_sha256"] == frozen["sha256"]
    assert diagnosis["cases"][0]["market_hypothesis_status"] == "snapshots_not_provided"
    assert diagnosis["summary"]["snapshots_not_provided"] == 1
