#!/usr/bin/env python3
"""Regenerate pilot-original-anchors/corpus-gap.json from teaser-cases.json.

Counts only original teaser/headline text — no Call-PDF leak, no enrichment.
issuer_literal alone does not count as a native specific anchor (≥2 named
relation/financial facts remain the gate).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scanner.hebeltrader.detective.investigation import _clues

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "hebeltrader" / "teaser-cases.json"
DEFAULT_OUT = (
    ROOT / "docs" / "examples" / "source-packets" / "pilot-original-anchors" / "corpus-gap.json"
)

NAMED_RELATIONS = (
    "acquisition",
    "merger",
    "partnership",
    "product_literal",
    "investment",
    "contract",
)


def _row_for_case(case: dict) -> dict:
    text = "\n".join(part for part in (case.get("headline"), case.get("teaser_text")) if part)
    clues = _clues(text, []) if text.strip() else []
    named_relation_facts = []
    other_fact_claims = []
    entities = []
    financial_metrics = 0
    for clue in clues:
        if clue.category == "financial_metric":
            financial_metrics += 1
            continue
        if clue.category != "fact_claims":
            continue
        normalized = clue.normalized or ""
        relation = normalized.split("|", 1)[0]
        if relation in NAMED_RELATIONS:
            named_relation_facts.append(normalized)
        else:
            other_fact_claims.append(normalized)
        if clue.quote and clue.quote not in entities:
            entities.append(clue.quote)
    native = len(named_relation_facts) + financial_metrics
    return {
        "case_id": case["case_id"],
        "publication_at": case.get("publication_at") is not None
        or bool(case.get("publication_date")),
        "named_relation_facts": named_relation_facts,
        "other_fact_claims": other_fact_claims,
        "financial_metrics": financial_metrics,
        "entities": entities,
        "native_specific_anchor_count": native,
    }


def build_gap(cases_path: Path) -> dict:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    rows = [_row_for_case(case) for case in payload.get("cases") or []]
    return {
        "schema_version": 1,
        "kind": "original_teaser_named_anchor_gap",
        "recorded_at": datetime.now(UTC).isoformat(),
        "recorded_note": (
            "Counts only original teaser/headline text — no Call-PDF leak, "
            "no developmental enrichment."
        ),
        "summary": {
            "cases": len(rows),
            "with_publication_at": sum(1 for r in rows if r["publication_at"]),
            "with_ge_2_specific_anchors": sum(
                1 for r in rows if r["native_specific_anchor_count"] >= 2
            ),
            "with_ge_1_named_relation_fact": sum(1 for r in rows if r["named_relation_facts"]),
            "with_ge_1_financial_metric": sum(1 for r in rows if r["financial_metrics"]),
            "with_any_entity": sum(1 for r in rows if r["entities"]),
        },
        "cases": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    gap = build_gap(args.cases)
    text = json.dumps(gap, indent=2, ensure_ascii=False) + "\n"
    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(gap["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
