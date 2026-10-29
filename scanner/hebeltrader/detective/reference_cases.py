"""Development-reference curator/exporter. Never imported by the scan process."""

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

REQUIRED = {
    "case_id",
    "headline",
    "teaser_text",
    "text_completeness",
    "publication_date",
    "publication_issue",
    "first_prediction",
    "first_prediction_confidence",
    "actual_company",
    "actual_ticker",
    "derivative_wkn",
    "outcome",
    "source_status",
    "key_clues",
    "contradicting_clues",
    "failure_analysis",
    "evidence_sources",
}
INPUT_FIELDS = ("case_id", "headline", "teaser_text", "publication_date", "publication_at")


def load_references(path):
    data = json.loads(Path(path).read_text())
    cases = data.get("cases", [])
    if len(cases) != 18 or len({c.get("case_id") for c in cases}) != 18:
        raise ValueError("Expected 18 uniquely identified historical cases")
    if {c.get("reference_number") for c in cases} != set(range(1, 19)):
        raise ValueError("Reference numbering must be complete")
    for case in cases:
        if not REQUIRED.issubset(case):
            raise ValueError("Reference missing required field")
        if case["outcome"] not in {"correct", "wrong", "unresolved"}:
            raise ValueError("Unknown historical outcome")
        if case["outcome"] == "unresolved" and any(
            case[k] is not None for k in ("actual_company", "actual_ticker", "derivative_wkn")
        ):
            raise ValueError("An unresolved case cannot have a claimed resolution")
        if case["outcome"] != "unresolved" and not case["actual_company"]:
            raise ValueError("Resolved case needs reported actual company")
        if case["publication_date"] is not None:
            date.fromisoformat(case["publication_date"])
        if case["text_completeness"] == "headline_only" and case["teaser_text"] is not None:
            raise ValueError("Headline-only case cannot contain invented original text")
        if case["text_completeness"] == "complete_user_supplied" and not case["teaser_text"]:
            raise ValueError("Full original missing")
    return data


def historical_summary(data):
    cases = data["cases"]
    counts = Counter(c["outcome"] for c in cases)
    return {
        "total": len(cases),
        "correct": counts["correct"],
        "wrong": counts["wrong"],
        "unresolved": counts["unresolved"],
        "resolved": counts["correct"] + counts["wrong"],
        "historical_conversation_percent": round(
            100 * counts["correct"] / (counts["correct"] + counts["wrong"]), 1
        ),
        "independent_benchmark": False,
        "missing_full_teasers": [c["case_id"] for c in cases if c["teaser_text"] is None],
        "missing_dates": [c["case_id"] for c in cases if c["publication_date"] is None],
        "missing_exact_timestamps": [
            c["case_id"] for c in cases if c.get("publication_at") is None
        ],
        "missing_original_top3": [c["case_id"] for c in cases if c.get("original_top3") is None],
        "wrong_cases": [
            {
                "case_id": c["case_id"],
                "first_prediction": c["first_prediction"],
                "actual_company": c["actual_company"],
                "failure_analysis": c["failure_analysis"],
            }
            for c in cases
            if c["outcome"] == "wrong"
        ],
    }


def export_inputs(source, destination):
    data = load_references(source)
    payload = {
        "schema_version": 1,
        "evaluation_class": "development_regression",
        "cases": [{key: c.get(key) for key in INPUT_FIELDS} for c in data["cases"]],
    }
    with Path(destination).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def markdown_table(data):
    lines = [
        (
            "| ID | Teaser / Kontext | Aktie / Ticker | Call-WKN | Status / Beleg | "
            "Besondere Umstände und offene Felder |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for c in sorted(data["cases"], key=lambda row: row["case_id"]):
        context = f"„{c['headline']}“"
        if c["publication_issue"]:
            context += f"; HEBELTRADER {c['publication_issue']}"
        if c["publication_date"]:
            context += "; " + date.fromisoformat(c["publication_date"]).strftime("%d.%m.%Y")
        company = c["actual_company"] or "Auflösung unbekannt; Verdacht: " + c["suspected_company"]
        if c["actual_ticker"]:
            company += f" ({c['actual_ticker']})"
        status = {
            "correct": "RICHTIG (Nutzerrekonstruktion)",
            "wrong": "FALSCH (Nutzerrekonstruktion)",
            "unresolved": "Ungelöst",
        }[c["outcome"]]
        notes = f"Ersttipp: {c['first_prediction']}. Nutzerfall {c['reference_number']:02d}. "
        if c["first_prediction_confidence"] is not None:
            notes += f"Historische unkalibrierte Angabe: {c['first_prediction_confidence']} %. "
        notes += c["failure_analysis"] or ""
        notes += (
            " Volltext vorhanden." if c["teaser_text"] else " Vollständiger Originalteaser fehlt."
        )
        if c["resolution_date"]:
            notes += f" Auflösung am {c['resolution_date']}; kein Publikationsdatum."
        values = [c["case_id"], context, company, c["derivative_wkn"] or "unbekannt", status, notes]
        lines.append(
            "| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values) + " |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "summary", "table"])
    parser.add_argument(
        "--references", type=Path, default=Path("data/hebeltrader/teaser-cases.json")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "export":
        if not args.output:
            parser.error("export needs --output; separate scan input file")
        export_inputs(args.references, args.output)
    elif args.command == "summary":
        print(
            json.dumps(
                historical_summary(load_references(args.references)), ensure_ascii=False, indent=2
            )
        )
    else:
        print(markdown_table(load_references(args.references)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
