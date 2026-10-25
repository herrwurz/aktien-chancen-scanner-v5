"""Per-teaser diagnosis: failure codes, Top-3, clue gaps — not a hit-rate claim."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from scanner.config import Settings
from scanner.hebeltrader.detective.clue_enrichment import HeuristicClueEnricher
from scanner.hebeltrader.detective.eu_universe import load_eu_dach_assets
from scanner.hebeltrader.detective.factory import build_detective
from scanner.hebeltrader.detective.hypothesis_source import HypothesisCandidateSource
from scanner.hebeltrader.detective.news_channel import FixtureNewsSearcher
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.service import DetectiveService


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _clue_summary(clues: list[dict]) -> dict:
    by_category: dict[str, list[str]] = {}
    for clue in clues:
        category = clue.get("category") or "unknown"
        value = clue.get("value") or clue.get("normalized") or ""
        by_category.setdefault(category, []).append(str(value)[:120])
    return {key: values for key, values in sorted(by_category.items())}


def summarize_result(case_id: str, teaser_text: str, result: dict, label: dict | None = None):
    identification = result.get("identification") or {}
    candidates = result.get("candidates") or []
    clues = result.get("extracted_clues") or []
    coverage = (result.get("candidate_source") or {}).get("coverage") or {}
    top3 = []
    for row in candidates[:3]:
        top3.append(
            {
                "asset_id": row.get("asset_id"),
                "name": row.get("name") or (row.get("identity") or {}).get("name"),
                "isin": row.get("isin") or (row.get("identity") or {}).get("isin"),
                "country": row.get("country"),
                "evidence_score": row.get("evidence_score"),
                "evidence_strength": row.get("evidence_strength"),
                "hypothesis_reasons": row.get("hypothesis_reasons") or [],
                "supporting_clues": row.get("supporting_clues") or [],
                "contradictions": row.get("contradictions") or [],
                "unknown_clue_count": len(row.get("unknown_clue_ids") or []),
                "hard_contradictions": bool(row.get("hard_contradictions")),
            }
        )
    status = identification.get("status")
    failure_code = identification.get("failure_code") or identification.get("reason")
    row = {
        "case_id": case_id,
        "teaser_sha256": _sha(teaser_text),
        "teaser_preview": teaser_text.replace("\n", " ").strip()[:160],
        "analysis_mode": result.get("analysis_mode"),
        "status": status,
        "failure_code": failure_code if status == "unresolved" else None,
        "decision_reason": identification.get("reason"),
        "selected_asset_id": identification.get("selected_asset_id"),
        "requires_manual_review": identification.get("requires_manual_review"),
        "clue_categories": _clue_summary(clues),
        "clue_count": len(clues),
        "search_queries": result.get("search_queries") or [],
        "top3": top3,
        "top3_asset_ids": [item["asset_id"] for item in top3],
        "visible_universe_size": coverage.get("visible_universe_size"),
        "matched_before_limit": coverage.get("matched_before_limit"),
        "stage_a_asset_ids": list(coverage.get("stage_a_asset_ids") or [])[:20],
        "review_hints": result.get("review_hints") or [],
    }
    if label is not None:
        acceptable = set(label.get("acceptable_asset_ids") or [])
        target = label.get("asset_id")
        hit = bool(acceptable and set(row["top3_asset_ids"]) & acceptable)
        in_top3 = target in row["top3_asset_ids"] if target else False
        row["label"] = {
            "asset_id": target,
            "acceptable_asset_ids": sorted(acceptable),
            "expected_in_universe": label.get("expected_in_universe"),
            "resolution_note": label.get("resolution_note"),
            "hit_acceptable_top3": hit,
            "target_in_top3": in_top3,
            "outcome": (
                "hit_top3"
                if hit or in_top3
                else "abstention_ok"
                if label.get("expected_in_universe") is False and status == "unresolved"
                else "false_top3"
                if status == "hypothesis_top3" and label.get("expected_in_universe") is False
                else "miss_top3"
                if label.get("expected_in_universe")
                else "unresolved"
            ),
        }
    return row


def diagnose_manifest(manifest_path: Path, service, labels: dict | None = None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    cases = []
    for case in manifest["cases"]:
        text = case["teaser_text"]
        result = service.analyze(
            DetectiveRequest(
                analysis_mode=case.get("analysis_mode", "hypothesis"),
                teaser_text=text,
                publication_at=case.get("publication_at"),
            )
        )
        label = labels.get(case["case_id"]) if labels else None
        cases.append(summarize_result(case["case_id"], text, result, label))
    outcome_counts: dict[str, int] = {}
    for row in cases:
        key = (row.get("label") or {}).get("outcome") or row.get("status") or "unknown"
        outcome_counts[key] = outcome_counts.get(key, 0) + 1
    return {
        "schema_version": 1,
        "kind": "detective_teaser_diagnosis",
        "corpus_kind": manifest.get("corpus_kind"),
        "case_count": len(cases),
        "outcome_counts": outcome_counts,
        "cases": cases,
        "limits": [
            "Diagnosis is not a calibrated hit rate.",
            "Synthetic or mini corpora do not prove real teaser accuracy.",
            "hypothesis_top3 always requires manual review.",
        ],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Detektiv-Teaser-Diagnose",
        "",
        f"Korpus: `{report.get('corpus_kind')}` · Fälle: **{report['case_count']}**",
        "",
        "Outcome-Zähler:",
        "",
    ]
    for key, value in sorted((report.get("outcome_counts") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Fälle", ""])
    for row in report["cases"]:
        label = row.get("label") or {}
        lines.append(f"### `{row['case_id']}`")
        lines.append("")
        lines.append(f"- Teaser: {row['teaser_preview']}")
        lines.append(f"- Status: `{row['status']}` · reason: `{row['decision_reason']}`")
        if row.get("failure_code"):
            lines.append(f"- Failure: `{row['failure_code']}`")
        if label:
            lines.append(
                f"- Label-Outcome: `{label.get('outcome')}`"
                f" · erwartet im Universum: `{label.get('expected_in_universe')}`"
            )
            if label.get("resolution_note"):
                lines.append(f"- Hinweis: {label['resolution_note']}")
        clue_json = json.dumps(row["clue_categories"], ensure_ascii=False)
        lines.append(f"- Hinweise ({row['clue_count']}): `{clue_json}`")
        if row["top3"]:
            lines.append("- Top-3:")
            for idx, cand in enumerate(row["top3"], start=1):
                lines.append(
                    f"  {idx}. `{cand['asset_id']}` {cand.get('name') or '?'} "
                    f"(score={cand.get('evidence_score')}, {cand.get('evidence_strength')}; "
                    f"reasons={cand.get('hypothesis_reasons')})"
                )
        else:
            lines.append("- Top-3: _(leer)_")
        lines.append("")
    lines.extend(["## Grenzen", ""])
    for item in report.get("limits") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_csv(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "status",
        "failure_code",
        "decision_reason",
        "outcome",
        "top3_asset_ids",
        "selected_asset_id",
        "clue_count",
        "teaser_preview",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["cases"]:
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "status": row["status"],
                    "failure_code": row.get("failure_code") or "",
                    "decision_reason": row.get("decision_reason") or "",
                    "outcome": (row.get("label") or {}).get("outcome") or "",
                    "top3_asset_ids": "|".join(row.get("top3_asset_ids") or []),
                    "selected_asset_id": row.get("selected_asset_id") or "",
                    "clue_count": row.get("clue_count"),
                    "teaser_preview": row.get("teaser_preview") or "",
                }
            )


def _hypothesis_fixture_service() -> DetectiveService:
    root = Path("tests/fixtures/detective-hypothesis")
    news = json.loads((root / "fixture_news.json").read_text(encoding="utf-8"))["items"]
    source = HypothesisCandidateSource(
        eu_assets=load_eu_dach_assets(),
        news_searcher=FixtureNewsSearcher(news),
    )
    return DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        enricher=HeuristicClueEnricher(),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path, help="Manifest with teaser cases")
    parser.add_argument("--labels", type=Path, help="Optional labels.json for outcome tagging")
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument(
        "--service",
        choices=("hypothesis_fixture", "settings"),
        default="hypothesis_fixture",
        help="hypothesis_fixture uses curated EU seed + fixture news; settings uses factory",
    )
    parser.add_argument("--research-mode", default="fixture")
    parser.add_argument("--research-index", type=Path)
    args = parser.parse_args(argv)

    labels = None
    if args.labels:
        labels = json.loads(args.labels.read_text(encoding="utf-8"))["cases"]

    if args.service == "hypothesis_fixture":
        service = _hypothesis_fixture_service()
    else:
        values = {"detective_research_mode": args.research_mode}
        if args.research_index:
            values["detective_research_index"] = args.research_index
        service = build_detective(Settings(_env_file=None, **values))

    report = diagnose_manifest(args.inputs, service, labels=labels)
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = Path(f"{prefix}.json")
    md_path = Path(f"{prefix}.md")
    csv_path = Path(f"{prefix}.csv")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    write_csv(report, csv_path)
    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "outcome_counts": report["outcome_counts"],
                "json": str(json_path),
                "markdown": str(md_path),
                "csv": str(csv_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
