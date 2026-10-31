"""Market chart as tie-break only — pad800 PIT hit rates without Blind score retune.

Uses committed corpus labels from ``teaser-cases.json`` for developmental hit
rates. Never mutates Blind 202/26 freeze SHA or chart score weights.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .featured_calls import blocked_features
from .market_screen import rank as market_rank
from .market_screen import resolve_case_snapshots

DEFAULT_SNAPSHOTS = Path("reports/snapshots-pit-pool-v1-pad800-2026-10-31.json")
DEFAULT_BLIND_SNAPSHOTS = Path("reports/snapshots-pit-pool-v1-remap-2026-10-30.json")
DEFAULT_MANIFEST = Path("docs/examples/source-packets/corpus-v1/manifest.json")
DEFAULT_ORIGINAL_GLOB = Path("docs/examples/source-packets/corpus-v1")
DEFAULT_FREEZE = Path("docs/examples/source-packets/corpus-v1/evidence-batch-corpus-v1.json")
DEFAULT_BLIND_INPUTS = Path("docs/examples/blind-202-26-inputs-with-publication-at.json")
BLIND_SOLUTION_TICKER = "DBK.XETRA"


def _teaser_blob(case: dict) -> str:
    return "\n".join(part for part in (case.get("headline"), case.get("teaser_text")) if part)


def _hit_rank(ranking: list[dict], ticker: str | None) -> int | None:
    if not ticker:
        return None
    wanted = {ticker, ticker.split(".")[0]}
    for index, row in enumerate(ranking, 1):
        candidate = row.get("ticker") or ""
        if candidate in wanted or candidate.split(".")[0] in wanted:
            return index
    return None


def load_corpus_original_cases(
    manifest_path: Path = DEFAULT_MANIFEST,
    corpus_dir: Path = DEFAULT_ORIGINAL_GLOB,
) -> list[dict]:
    """Original teaser inputs + manifest expected_ticker (developmental labels)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {c["case_id"]: c["expected_ticker"] for c in manifest["cases"]}
    cases = []
    for case_id, ticker in sorted(expected.items()):
        path = corpus_dir / f"{case_id}.inputs.original.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        row = dict(payload["cases"][0])
        row["expected_ticker"] = ticker
        cases.append(row)
    return cases


def evaluate_market_hits(
    *,
    snapshots: dict,
    cases: list[dict],
    limit: int = 8,
) -> dict:
    rows = []
    for case in cases:
        case_id = case["case_id"]
        ticker = case.get("expected_ticker") or case.get("actual_ticker")
        graded = bool(ticker)
        pub_date = case.get("publication_date")
        blob = _teaser_blob(case)
        if not pub_date or not blob.strip():
            rows.append(
                {
                    "case_id": case_id,
                    "ticker": ticker,
                    "graded": False,
                    "market_hit_rank": None,
                    "status": "missing_publication_date_or_text",
                    "market_top8": [],
                    "chart_clues": [],
                }
            )
            continue
        resolved = resolve_case_snapshots(snapshots, pub_date)
        if resolved["status"] != "ok" or not resolved.get("snapshots"):
            rows.append(
                {
                    "case_id": case_id,
                    "ticker": ticker,
                    "graded": graded,
                    "market_hit_rank": None,
                    "status": resolved["status"],
                    "market_top8": [],
                    "chart_clues": [],
                    "coverage": resolved.get("snapshot_coverage"),
                }
            )
            continue
        blocked = blocked_features(pub_date)
        market = market_rank(blob, resolved["snapshots"], limit=limit, blocked=blocked)
        hit = _hit_rank(market["ranking"], ticker)
        rows.append(
            {
                "case_id": case_id,
                "ticker": ticker,
                "graded": graded,
                "market_hit_rank": hit if graded else None,
                "status": "ok",
                "market_top8": [r["ticker"] for r in market["ranking"]],
                "chart_clues": market["clues"],
                "coverage": market["snapshot_coverage"],
                "excluded_recent_calls": len(blocked.get("entries") or []),
            }
        )
    graded_rows = [r for r in rows if r["graded"] and r["status"] == "ok"]
    return {
        "graded": len(graded_rows),
        "top1": sum(1 for r in graded_rows if r["market_hit_rank"] == 1),
        "top3": sum(
            1 for r in graded_rows if r["market_hit_rank"] is not None and r["market_hit_rank"] <= 3
        ),
        "top8": sum(
            1 for r in graded_rows if r["market_hit_rank"] is not None and r["market_hit_rank"] <= 8
        ),
        "with_hypotheses": sum(1 for r in rows if r["market_top8"]),
        "rows": rows,
    }


def packet_leader_confirmation(freeze: dict, market_rows: list[dict]) -> dict:
    """How often pad800 market Top-8 contains the named packet leader (tie-break confirm)."""
    by_id = {r["case_id"]: r for r in market_rows}
    named = [r for r in freeze.get("rows") or [] if "named" in Path(r.get("inputs") or "").name]
    confirmed = []
    missed = []
    for row in named:
        if row.get("identification_status") != "identified":
            continue
        leader = row.get("packet_evidence_ticker")
        market = by_id.get(row["case_id"]) or {}
        top8 = market.get("market_top8") or []
        hit = _hit_rank([{"ticker": t} for t in top8], leader)
        entry = {
            "case_id": row["case_id"],
            "packet_leader": leader,
            "market_hit_rank": hit,
            "market_top8": top8,
        }
        if hit is not None:
            confirmed.append(entry)
        else:
            missed.append(entry)
    return {
        "named_identified": len(confirmed) + len(missed),
        "market_confirms_in_top8": len(confirmed),
        "market_misses_top8": len(missed),
        "confirmed": confirmed,
        "missed": missed,
    }


def original_packet_gap(freeze: dict) -> dict:
    originals = [
        r for r in freeze.get("rows") or [] if "original" in Path(r.get("inputs") or "").name
    ]
    by_status = {}
    for row in originals:
        status = row.get("packet_evidence_status") or "unknown"
        by_status.setdefault(status, []).append(
            {
                "case_id": row["case_id"],
                "ticker": row.get("packet_evidence_ticker"),
                "confirmed_specific_clues": row.get("confirmed_specific_clues"),
                "score_margin": row.get("score_margin"),
            }
        )
    return {
        "total": len(originals),
        "identified": sum(1 for r in originals if r.get("identification_status") == "identified"),
        "by_packet_evidence_status": {
            status: {"count": len(rows), "cases": rows}
            for status, rows in sorted(by_status.items())
        },
    }


def blind_dbk_rank(snapshots: dict, blind_inputs: dict, *, limit: int = 8) -> dict:
    case = blind_inputs["cases"][0]
    pub_date = case.get("publication_date")
    blob = _teaser_blob(case)
    resolved = resolve_case_snapshots(snapshots, pub_date)
    if resolved["status"] != "ok":
        return {"status": resolved["status"], "in_top8": False}
    blocked = blocked_features(pub_date)
    # Full ranking for DBK position (not truncated).
    market = market_rank(blob, resolved["snapshots"], limit=10_000, blocked=blocked)
    ranking = market["ranking"]
    top8 = [r["ticker"] for r in ranking[:limit]]
    dbk_rank = _hit_rank(ranking, BLIND_SOLUTION_TICKER)
    dbk_score = next(
        (r["score"] for r in ranking if r.get("ticker") == BLIND_SOLUTION_TICKER), None
    )
    score_23 = sum(1 for r in ranking if r.get("score") == 23)
    return {
        "status": "ok",
        "in_top8": bool(dbk_rank is not None and dbk_rank <= limit),
        "top8": top8,
        "dbk_rank": dbk_rank,
        "dbk_score": dbk_score,
        "coverage": market["snapshot_coverage"],
        "ranked_before_limit": market["ranked_before_limit"],
        "names_at_score_23": score_23,
        "note": (
            "Developmental residual B_chart_rank. Blind freeze SHA untouched; "
            "no chart score retuning."
        ),
    }


def build_report(
    *,
    snapshots_path: Path,
    freeze_path: Path,
    blind_inputs_path: Path,
    blind_snapshots_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    corpus_dir: Path = DEFAULT_ORIGINAL_GLOB,
) -> dict:
    snapshots = json.loads(snapshots_path.read_text(encoding="utf-8"))
    cases = load_corpus_original_cases(manifest_path, corpus_dir)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    blind_inputs = json.loads(blind_inputs_path.read_text(encoding="utf-8"))
    blind_snapshots = (
        json.loads(blind_snapshots_path.read_text(encoding="utf-8"))
        if blind_snapshots_path.exists()
        else snapshots
    )
    market = evaluate_market_hits(snapshots=snapshots, cases=cases)
    blind = blind_dbk_rank(blind_snapshots, blind_inputs)
    blind["snapshots"] = str(
        blind_snapshots_path if blind_snapshots_path.exists() else snapshots_path
    )
    return {
        "schema_version": 1,
        "kind": "hebeltrader-market-tiebreak-pad800-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "snapshots": str(snapshots_path),
        "history_pad_days": 800,
        "policy": [
            "Charts are tie-break / suggestion only — never identification.",
            "Blind 202/26 freeze SHA and chart weights are not retuned here.",
            "Named packet leaders remain the identification channel (Stufe 3a).",
            "Original teasers remain 0 identified without ≥2 native named anchors.",
        ],
        "market": {
            "graded": market["graded"],
            "top1": market["top1"],
            "top3": market["top3"],
            "top8": market["top8"],
            "with_hypotheses": market["with_hypotheses"],
        },
        "packet_leader_confirmation": packet_leader_confirmation(freeze, market["rows"]),
        "original_packet_gap": original_packet_gap(freeze),
        "blind_202_26": blind,
        "cases": market["rows"],
    }


def render_text(report: dict) -> str:
    market = report["market"]
    confirm = report["packet_leader_confirmation"]
    originals = report["original_packet_gap"]
    blind = report["blind_202_26"]
    lines = [
        "market tie-break (pad800 PIT)",
        f"  market graded Top1/3/8: {market['top1']}/{market['top3']}/{market['top8']}"
        f" of {market['graded']}",
        f"  named packet leaders in market Top-8: "
        f"{confirm['market_confirms_in_top8']}/{confirm['named_identified']}",
        f"  originals identified: {originals['identified']}/{originals['total']}",
        (
            f"  Blind DBK rank: {blind.get('dbk_rank')} "
            f"(in_top8={blind.get('in_top8')}, score={blind.get('dbk_score')})"
        ),
        "  Blind freeze SHA untouched; no score retune.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument(
        "--blind-snapshots",
        type=Path,
        default=DEFAULT_BLIND_SNAPSHOTS,
        help="PIT file that includes Blind as_of 2026-10-30 (pad800 corpus dates stop at 10-29)",
    )
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--blind-inputs", type=Path, default=DEFAULT_BLIND_INPUTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_ORIGINAL_GLOB)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.snapshots.exists():
        raise SystemExit(
            f"missing snapshots {args.snapshots}; export pad800 PIT under reports/ first"
        )
    report = build_report(
        snapshots_path=args.snapshots,
        freeze_path=args.freeze,
        blind_inputs_path=args.blind_inputs,
        blind_snapshots_path=args.blind_snapshots,
        manifest_path=args.manifest,
        corpus_dir=args.corpus_dir,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
