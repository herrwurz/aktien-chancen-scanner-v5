import json


def test_hs5rmp_report_blocks_return_without_quotes_and_keeps_tiingo_separate():
    from scanner.hebeltrader.derivative_coverage import build_hs5rmp_coverage

    report = build_hs5rmp_coverage(
        product_terms={"wkn": "HS5RMP", "review_status": "pending"},
        quote_archive=None,
        tiingo={
            "request": {"symbol": "JNJ", "start": "2025-08-05", "end": "2026-01-16"},
            "raw_sha256": "a" * 64,
            "payload": [{"date": "2025-08-05T00:00:00Z"}] * 115,
        },
    )
    assert report["instrument"] == "HS5RMP"
    assert report["derivative_result"]["return_pct"] is None
    assert report["derivative_result"]["status"] == "blocked"
    assert "historical_bid_ask_unavailable" in report["blockers"]
    assert report["underlying_plausibility"]["observations"] == 115
    assert report["underlying_plausibility"]["may_replace_derivative_quotes"] is False


def test_acquisition_priority_matrix_is_deterministic_for_118_recommendations(tmp_path):
    from scanner.hebeltrader.derivative_coverage import prioritize_acquisition, write_coverage

    rows = []
    states = [
        ("verified_executable_quotes", True, "approved"),
        ("restricted_archive", True, "partial"),
        ("terms_only", True, "missing"),
        ("insufficient_data", False, "missing"),
    ]
    for index in range(118):
        expected, terms, quotes = states[index % len(states)]
        rows.append(
            {
                "recommendation_key": f"sha-{index}:1",
                "derivative_wkn": f"W{index:05d}"[-6:],
                "terms_available": terms,
                "quote_availability": quotes,
                "expected": expected,
            }
        )
    report = prioritize_acquisition(rows)
    assert report["recommendation_count"] == 118
    assert sum(report["counts"].values()) == 118
    assert all(row["priority"] == row.pop("expected") for row in report["rows"])
    first = write_coverage(tmp_path / "first", report)
    second = write_coverage(tmp_path / "second", report)
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]
    assert json.loads(first[0].read_bytes())["recommendation_count"] == 118


def test_priority_never_uses_all_half_fail_labels():
    from scanner.hebeltrader.derivative_coverage import prioritize_acquisition

    rows = [
        {
            "recommendation_key": "sha:1",
            "derivative_wkn": "HS5RMP",
            "terms_available": True,
            "quote_availability": "missing",
            "source_categories": ["all", "fail"],
        }
    ]
    report = prioritize_acquisition(rows)
    assert report["rows"][0]["priority"] == "terms_only"
    assert "source_categories" not in report["rows"][0]


def test_readonly_priority_cli_writes_reproducible_matrix(tmp_path):
    from scanner.hebeltrader.derivatives_cli import main

    source = tmp_path / "recommendations.json"
    source.write_text(
        json.dumps(
            [
                {
                    "recommendation_key": "sha:1",
                    "derivative_wkn": "HS5RMP",
                    "terms_available": True,
                    "quote_availability": "missing",
                }
            ]
        )
    )
    prefix = tmp_path / "coverage"
    assert main(["prioritize", "--input", str(source), "--output-prefix", str(prefix)]) == 0
    assert json.loads((tmp_path / "coverage.json").read_bytes())["counts"]["terms_only"] == 1
