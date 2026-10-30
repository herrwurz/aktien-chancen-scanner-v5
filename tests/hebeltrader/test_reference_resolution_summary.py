"""Reference-data regressions; standard-library runner, no live research."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "reference_cases", ROOT / "scanner/hebeltrader/detective/reference_cases.py"
)
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)
DATA = ROOT / "data/hebeltrader/teaser-cases.json"


class ResolutionSummaryTests(unittest.TestCase):
    def test_counts_keep_reference_only_and_abstention_separate(self):
        data = REF.load_references(DATA)
        counts = {key: sum(c["outcome"] == key for c in data["cases"]) for key in (
            "correct", "wrong", "unresolved", "not_identified", "not_tested"
        )}
        self.assertEqual(counts, {
            "correct": 12, "wrong": 7, "unresolved": 1,
            "not_identified": 1, "not_tested": 7,
        })
        historical = REF.historical_summary(data)
        self.assertEqual(
            (historical["total"], historical["correct"], historical["wrong"],
             historical["unresolved"]), (18, 10, 7, 1)
        )

    def test_confirmation_does_not_invent_original_call_or_scanner_success(self):
        by = {c["reference_number"]: c for c in REF.load_references(DATA)["cases"]}
        self.assertEqual(by[28]["original_top3"], ["Deutsche Bank", "Commerzbank", "UBS"])
        self.assertEqual(by[28]["first_prediction"], by[28]["actual_company"])
        self.assertIsNone(by[28]["derivative_wkn"])
        self.assertFalse(by[28]["autonomous_scanner_success"])
        self.assertFalse(by[28]["independent_benchmark"])
        self.assertEqual(by[19]["resolution_history"][0]["prior_outcome"], "unresolved")
        self.assertEqual(by[19]["actual_ticker"], "SLB")
        self.assertEqual(by[20]["outcome"], "not_identified")

    def test_export_never_includes_resolution_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "inputs.json"
            REF.export_inputs(DATA, output)
            data = json.loads(output.read_text())
        allowed = {"case_id", "headline", "teaser_text", "publication_date", "publication_at"}
        self.assertTrue(all(set(c) == allowed for c in data["cases"]))
        db = next(c for c in data["cases"] if c["case_id"] == "HT-028")
        self.assertNotIn("Deutsche Bank", db["teaser_text"])
        self.assertNotIn("actual_company", db)


if __name__ == "__main__":
    unittest.main()
