import csv
import json
from datetime import date, timedelta
from pathlib import Path


def _bar(day, close):
    return {
        "date": day.isoformat(),
        "open": str(close),
        "high": str(close + 1),
        "low": str(close - 1),
        "close": str(close),
        "adjusted_close": str(close),
        "dividend_cash": "0",
        "split_factor": "1",
    }


def _assumptions():
    from tests.hebeltrader.test_derivative_model import _historical_assumptions

    return _historical_assumptions()


def _write_inputs(tmp_path):
    prior = [
        _bar(date(2025, 1, 1) + timedelta(days=index), 150 + index / 10) for index in range(146)
    ]
    current = [
        _bar(date(2025, 8, 5), 170),
        _bar(date(2025, 8, 6), 171),
        _bar(date(2025, 8, 7), 172),
    ]
    paths = {
        name: tmp_path / name
        for name in ("current.json", "prior.json", "fx.csv", "audit.json", "assumptions.json")
    }
    paths["current.json"].write_text(
        json.dumps({"provider": "Tiingo", "manifest_sha256": "c" * 64, "bars": current})
    )
    paths["prior.json"].write_text(json.dumps({"provider": "Tiingo", "bars": prior}))
    with paths["fx.csv"].open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["date", "usd_per_eur"])
        writer.writeheader()
        writer.writerows(
            [
                {"date": "2025-08-04", "usd_per_eur": "1.15"},
                {"date": "2025-08-05", "usd_per_eur": "1.1546"},
                {"date": "2025-08-06", "usd_per_eur": "1.16"},
            ]
        )
    paths["audit.json"].write_text(json.dumps({"source": "synthetic", "verified": False}))
    paths["assumptions.json"].write_text(json.dumps(_assumptions()))
    return paths


def test_scenario_cli_uses_external_historical_files_and_binds_provenance(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    paths = _write_inputs(tmp_path)
    output = tmp_path / "report.json"
    result = main(
        [
            "scenario",
            "--underlying",
            str(paths["current.json"]),
            "--prehistory",
            str(paths["prior.json"]),
            "--fx",
            str(paths["fx.csv"]),
            "--input-audit",
            str(paths["audit.json"]),
            "--expected-underlying-manifest-sha256",
            "c" * 64,
            "--expected-current-sessions",
            "3",
            "--expected-prehistory-prices",
            "146",
            "--expected-fx-fixings",
            "3",
            "--assumptions",
            str(paths["assumptions.json"]),
            "--publication-at",
            "2025-08-05T08:15:00+02:00",
            "--output",
            str(output),
        ]
    )
    assert result == 0
    report = json.loads(output.read_bytes())
    assert report["status"] == "three_mode_report"
    assert report["historical_market_input_quality"]["prehistory_price_count"] == 146
    assert set(report["historical_market_input_provenance"]) == {
        "underlying_sha256",
        "prehistory_sha256",
        "fx_sha256",
        "audit_sha256",
    }
    assert report["modes"]["MODELED_DERIVATIVE"]["market_input_mode"] == "point_in_time_historical"


def test_scenario_cli_rejects_partial_historical_file_set(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    paths = _write_inputs(tmp_path)
    result = main(
        [
            "scenario",
            "--underlying",
            str(paths["current.json"]),
            "--prehistory",
            str(paths["prior.json"]),
            "--assumptions",
            str(paths["assumptions.json"]),
            "--publication-at",
            "2025-08-05T08:15:00+02:00",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )
    assert result == 2


def test_scenario_cli_rejects_manifest_or_coverage_mismatch_before_model(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    paths = _write_inputs(tmp_path)
    result = main(
        [
            "scenario",
            "--underlying",
            str(paths["current.json"]),
            "--prehistory",
            str(paths["prior.json"]),
            "--fx",
            str(paths["fx.csv"]),
            "--input-audit",
            str(paths["audit.json"]),
            "--expected-underlying-manifest-sha256",
            "d" * 64,
            "--expected-current-sessions",
            "115",
            "--assumptions",
            str(paths["assumptions.json"]),
            "--publication-at",
            "2025-08-05T08:15:00+02:00",
            "--output",
            str(tmp_path / "must-not-exist.json"),
        ]
    )
    assert result == 2
    assert not (tmp_path / "must-not-exist.json").exists()


def test_batch_readiness_never_runs_unverified_product_models():
    from scanner.hebeltrader.historical_inputs import audit_batch_readiness

    report = audit_batch_readiness(
        [
            {
                "recommendation_id": "sha:1",
                "input_files": {"underlying": "a", "prehistory": "b", "fx": "c", "audit": "d"},
                "product_evidence_status": "unverified",
            }
        ]
    )
    assert report["items"][0]["status"] == "blocked_unverified_product_terms"
    assert report["items"][0]["model_executed"] is False
    assert report["modeled_count"] == 0


def test_repository_v19_assumptions_are_historical_and_explicitly_hypothetical():
    assumptions = json.loads(
        Path("docs/hebeltrader-hs5rmp-model-assumptions-v19.example.json").read_bytes()
    )
    assert "fx_usd_per_eur" not in assumptions["product"]
    assert assumptions["product"]["parameter_status"] == "hypothetical"
    assert assumptions["reference_prices"]["indicative_call_price"] == "0.17"
    assert {
        (value["volatility_window"], value["iv_multiplier"])
        for value in assumptions["scenarios"].values()
    } == {("120", "0.85"), ("60", "1.00"), ("20", "1.15")}


def test_v20_cli_is_opt_in_and_keeps_v19_scenario_command(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    paths = _write_inputs(tmp_path)
    assumptions = json.loads(paths["assumptions.json"].read_bytes())
    assumptions["v20_analysis"] = {
        "iv_stress_path": {
            "sessions": 20,
            "status": "hypothetical_explicit_stress",
        },
        "slippage": {
            "zero": "0",
            "stress": "0.25",
            "stress_rationale": "synthetic regression assumption",
        },
    }
    paths["assumptions.json"].write_text(json.dumps(assumptions))
    output = tmp_path / "v20.json"
    result = main(
        [
            "scenario-v20",
            "--underlying",
            str(paths["current.json"]),
            "--prehistory",
            str(paths["prior.json"]),
            "--fx",
            str(paths["fx.csv"]),
            "--input-audit",
            str(paths["audit.json"]),
            "--assumptions",
            str(paths["assumptions.json"]),
            "--publication-at",
            "2025-08-05T08:15:00+02:00",
            "--output",
            str(output),
        ]
    )
    assert result == 0
    report = json.loads(output.read_bytes())
    assert report["status"] == "hypothetical_v20_iv_attribution"
    assert report["base_v19_report"]["status"] == "three_mode_report"
    assert report["observed_hs5rmp_quotes_used"] is False
    markdown = output.with_suffix(".md").read_text()
    assert "Historische Datenqualität" in markdown
    assert "IV-Pfade und Handelsergebnisse" in markdown
    assert "Keine beobachteten HS5RMP" in markdown
    assert "Produktparameter-Sensitivität" in markdown
