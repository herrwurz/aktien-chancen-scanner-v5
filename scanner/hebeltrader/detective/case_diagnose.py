"""Solution-free per-case diagnosis from frozen rankings (and optional live screens).

Emits clues, sector hits, snapshot coverage and Top-8 structure/market hypotheses.
Never claims identification and never reads solution/reference label files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .case_journal import read_frozen
from .market_screen import rank as market_rank
from .market_screen import resolve_case_snapshots, teaser_chart_clues
from .structure_screen import screen, sectors_in


def _compact_hypothesis(item):
    return {
        key: item[key]
        for key in ("name", "ticker", "sector", "layer", "structure", "score")
        if key in item and item[key] is not None
    }


def diagnose_report(report):
    """Summarise one frozen analysis case without inventing evidence."""
    meta = report.get("market_hypothesis_meta") or {}
    offline = [_compact_hypothesis(item) for item in report.get("offline_hypotheses") or []]
    market = [_compact_hypothesis(item) for item in report.get("market_hypotheses") or []]
    identification = report.get("identification") or {}
    return {
        "case_id": report.get("case_id"),
        "identification_status": identification.get("status"),
        "input_completeness": report.get("reference_input_completeness"),
        "source_packet_status": report.get("source_packet_status"),
        "chart_clues": list(meta.get("clues") or []),
        "sectors_named": list(meta.get("sectors") or []),
        "offline_hypothesis_status": report.get("offline_hypothesis_status"),
        "offline_hypotheses": offline,
        "market_hypothesis_status": meta.get("status"),
        "snapshot_as_of": meta.get("snapshot_as_of"),
        "snapshot_coverage": meta.get("snapshot_coverage"),
        "ranked_before_limit": meta.get("ranked_before_limit"),
        "market_hypotheses": market,
        "interpretation": (
            "Unverified local hypotheses only; chart/sector matches are not identifications."
        ),
    }


def diagnose_frozen(rankings):
    frozen = read_frozen(rankings)
    cases = [diagnose_report(report) for report in frozen["report"]["cases"]]
    return {
        "ranking_sha256": frozen["sha256"],
        "evaluation_class": frozen["report"].get("evaluation_class"),
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "with_offline_hypotheses": sum(1 for c in cases if c["offline_hypotheses"]),
            "with_market_hypotheses": sum(1 for c in cases if c["market_hypotheses"]),
            "snapshots_not_provided": sum(
                1 for c in cases if c["market_hypothesis_status"] == "snapshots_not_provided"
            ),
        },
    }


def diagnose_inputs(inputs, snapshots=None, *, limit=8):
    """Run structure/market screens on scan inputs without freezing a full investigation."""
    payload = json.loads(Path(inputs).read_text(encoding="utf-8"))
    snap_payload = None
    if snapshots is not None:
        snap_payload = json.loads(Path(snapshots).read_text(encoding="utf-8"))
    cases = []
    for case in payload["cases"]:
        blob = "\n".join(part for part in (case.get("headline"), case.get("teaser_text")) if part)
        offline = [_compact_hypothesis(item) for item in screen(blob, limit=limit)]
        chart_clues = teaser_chart_clues(blob)
        sectors = sectors_in(blob)
        as_of = None
        coverage = None
        ranked_before = None
        if snap_payload is None:
            market = []
            market_status = "snapshots_not_provided"
        else:
            resolved = resolve_case_snapshots(snap_payload, case.get("publication_date"))
            as_of = resolved.get("snapshot_as_of")
            if resolved["status"] != "ok" or not resolved["snapshots"]:
                market = []
                market_status = resolved["status"]
            else:
                ranked = market_rank(blob, resolved["snapshots"], limit=limit)
                market = [_compact_hypothesis(item) for item in ranked["ranking"]]
                coverage = ranked["snapshot_coverage"]
                ranked_before = ranked["ranked_before_limit"]
                market_status = (
                    "unverified_chart_universe_suggestions" if market else "no_market_hypotheses"
                )
        cases.append(
            {
                "case_id": case["case_id"],
                "identification_status": None,
                "input_completeness": ("complete" if case.get("teaser_text") else "headline_only"),
                "source_packet_status": None,
                "chart_clues": chart_clues,
                "sectors_named": sectors,
                "offline_hypothesis_status": (
                    "unverified_sector_universe_suggestions"
                    if offline
                    else "no_local_sector_hypotheses"
                ),
                "offline_hypotheses": offline,
                "market_hypothesis_status": market_status,
                "snapshot_as_of": as_of,
                "snapshot_coverage": coverage,
                "ranked_before_limit": ranked_before,
                "market_hypotheses": market,
                "interpretation": (
                    "Unverified local hypotheses only; chart/sector matches are not "
                    "identifications."
                ),
            }
        )
    return {
        "ranking_sha256": None,
        "evaluation_class": payload.get("evaluation_class"),
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "with_offline_hypotheses": sum(1 for c in cases if c["offline_hypotheses"]),
            "with_market_hypotheses": sum(1 for c in cases if c["market_hypotheses"]),
            "snapshots_not_provided": sum(
                1 for c in cases if c["market_hypothesis_status"] == "snapshots_not_provided"
            ),
        },
    }


def render_markdown(diagnosis):
    lines = [
        "# Case diagnosis (solution-free)",
        "",
        f"- cases: {diagnosis['summary']['cases']}",
        f"- with offline hypotheses: {diagnosis['summary']['with_offline_hypotheses']}",
        f"- with market hypotheses: {diagnosis['summary']['with_market_hypotheses']}",
        f"- snapshots not provided: {diagnosis['summary']['snapshots_not_provided']}",
    ]
    if diagnosis.get("ranking_sha256"):
        lines.append(f"- ranking_sha256: `{diagnosis['ranking_sha256']}`")
    lines.append("")
    for case in diagnosis["cases"]:
        lines.extend(
            [
                f"## {case['case_id']}",
                "",
                f"- input: {case.get('input_completeness')}",
                f"- identification: {case.get('identification_status')}",
                f"- chart clues: {', '.join(case['chart_clues']) or '—'}",
                f"- sectors: {', '.join(case['sectors_named']) or '—'}",
                f"- offline: {case['offline_hypothesis_status']}",
                f"- market: {case['market_hypothesis_status']}"
                + (
                    f" (coverage={case['snapshot_coverage']})"
                    if case.get("snapshot_coverage") is not None
                    else ""
                ),
                "",
            ]
        )
        if case["offline_hypotheses"]:
            lines.append("Offline Top-8:")
            for item in case["offline_hypotheses"]:
                lines.append(
                    f"- {item.get('name')} ({item.get('ticker') or '—'}) [{item.get('sector')}]"
                )
            lines.append("")
        if case["market_hypotheses"]:
            lines.append("Market Top-8:")
            for item in case["market_hypotheses"]:
                score = item.get("score")
                score_bit = f" score={score}" if score is not None else ""
                lines.append(f"- {item.get('name')} ({item.get('ticker') or '—'}){score_bit}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rankings", type=Path, help="Frozen rankings.json")
    group.add_argument("--inputs", type=Path, help="Scan inputs JSON (no freeze)")
    parser.add_argument("--snapshots", type=Path, help="Optional market_screen export")
    parser.add_argument("--output", type=Path, required=True, help="Write diagnosis JSON")
    parser.add_argument(
        "--markdown",
        type=Path,
        help="Optional markdown twin of the diagnosis JSON",
    )
    args = parser.parse_args(argv)
    if args.rankings:
        if args.snapshots:
            parser.error("--snapshots only applies with --inputs")
        diagnosis = diagnose_frozen(args.rankings)
    else:
        diagnosis = diagnose_inputs(args.inputs, args.snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(diagnosis, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(diagnosis), encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": diagnosis["summary"]["cases"],
                "with_market_hypotheses": diagnosis["summary"]["with_market_hypotheses"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
