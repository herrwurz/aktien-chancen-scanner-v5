#!/usr/bin/env python3
"""Promote provisional publication_at once operator PDFs confirm Stand Uhr.

HT-003 (Costco 192/26) and HT-012 (BASF 137/26) currently use
``featured_date + corpus Stand 08:15`` overlays. When the matching publisher
PDFs appear in the inventory with a ``publication_at_guess``, this script
rewrites the provisional overlay and (with ``--apply-shared-refs``) fills
``reference-27-inputs-with-publication-at.json``.

HT-016 remains blocked (issue 191/26 bound; Call-PDF Stand Uhr still missing)
and is never promoted here.

Default is dry-run. Pass ``--apply`` to write files.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PENDING = {
    "HT-003": {
        "issue": "192/26",
        "company_hint": "Costco",
        "provisional_path_keys": ("featured_issue",),
    },
    "HT-012": {
        "issue": "137/26",
        "company_hint": "BASF",
        "provisional_path_keys": ("featured_issue",),
    },
}

BLOCKED = {
    "HT-016": "issue_191_26_bound_awaiting_pdf_stand_unresolved_identity",
}

INVENTORY = ROOT / "docs" / "hebeltrader-publisher-pdf-inventory.json"
PROVISIONAL_REFS = (
    ROOT
    / "docs"
    / "examples"
    / "source-packets"
    / "batch-pending-pdf"
    / "refs-provisional-publication-at.json"
)
SHARED_REFS = ROOT / "docs" / "examples" / "reference-27-inputs-with-publication-at.json"
PENDING_MANIFEST = (
    ROOT / "docs" / "examples" / "source-packets" / "batch-pending-pdf" / "manifest.json"
)
PENDING_SUMMARY = (
    ROOT
    / "docs"
    / "examples"
    / "source-packets"
    / "batch-pending-pdf"
    / "packet-build-summary.json"
)

PDF_CONFIRMED_BASIS = "publisher_pdf_stand_uhr"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _inventory_hits(inventory: dict) -> dict[str, dict]:
    """Map case_id → best inventory PDF row for the required issue."""
    by_issue = {}
    for row in inventory.get("pdfs") or []:
        issue = row.get("issue")
        if not issue:
            continue
        by_issue.setdefault(issue, []).append(row)

    hits = {}
    for case_id, spec in PENDING.items():
        rows = by_issue.get(spec["issue"]) or []
        # Prefer rows with a Stand guess; then prefer label hint match.
        ranked = sorted(
            rows,
            key=lambda r: (
                0 if r.get("publication_at_guess") else 1,
                0
                if spec["company_hint"].casefold() in (r.get("label_hint") or "").casefold()
                else 1,
                r.get("filename") or "",
            ),
        )
        if ranked:
            hits[case_id] = ranked[0]
    return hits


def plan_promotions(inventory: dict, provisional: dict) -> dict:
    hits = _inventory_hits(inventory)
    actions = []
    for case_id, spec in PENDING.items():
        overlay = next((c for c in provisional["cases"] if c["case_id"] == case_id), None)
        hit = hits.get(case_id)
        if hit is None:
            actions.append(
                {
                    "case_id": case_id,
                    "status": "still_missing_pdf",
                    "required_issue": spec["issue"],
                    "company_hint": spec["company_hint"],
                }
            )
            continue
        guess = hit.get("publication_at_guess")
        if not guess:
            actions.append(
                {
                    "case_id": case_id,
                    "status": "pdf_present_but_no_stand_guess",
                    "required_issue": spec["issue"],
                    "filename": hit.get("filename"),
                }
            )
            continue
        if overlay and overlay.get("publication_at_basis") == PDF_CONFIRMED_BASIS:
            if overlay.get("publication_at") == guess:
                actions.append(
                    {
                        "case_id": case_id,
                        "status": "already_promoted",
                        "publication_at": guess,
                        "filename": hit.get("filename"),
                    }
                )
                continue
        actions.append(
            {
                "case_id": case_id,
                "status": "ready_to_promote",
                "required_issue": spec["issue"],
                "from_publication_at": (overlay or {}).get("publication_at"),
                "to_publication_at": guess,
                "from_basis": (overlay or {}).get("publication_at_basis"),
                "to_basis": PDF_CONFIRMED_BASIS,
                "filename": hit.get("filename"),
                "publication_date": hit.get("publication_date"),
            }
        )
    return {
        "schema_version": 1,
        "kind": "hebeltrader-provisional-publication-at-promote-plan-v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "blocked": [{"case_id": k, "reason": v} for k, v in BLOCKED.items()],
        "actions": actions,
        "ready": sum(1 for a in actions if a["status"] == "ready_to_promote"),
        "still_missing": sum(1 for a in actions if a["status"] == "still_missing_pdf"),
    }


def apply_promotions(plan: dict, *, apply_shared_refs: bool) -> dict:
    ready = [a for a in plan["actions"] if a["status"] == "ready_to_promote"]
    if not ready:
        return {"wrote": [], "note": "nothing_ready"}

    wrote = []
    provisional = _load(PROVISIONAL_REFS)
    by_id = {c["case_id"]: c for c in provisional["cases"]}
    for action in ready:
        case = by_id[action["case_id"]]
        case["publication_at"] = action["to_publication_at"]
        case["publication_date"] = action.get("publication_date") or case.get("publication_date")
        case["publication_at_basis"] = PDF_CONFIRMED_BASIS
        case["promoted_from_pdf"] = action["filename"]
        case["promoted_at"] = plan["recorded_at"]
    provisional["note"] = (
        "Promoted from publisher PDF Stand Uhr where ready; remaining gaps stay provisional."
    )

    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT))
        except ValueError:
            return str(path)

    _write(PROVISIONAL_REFS, provisional)
    wrote.append(_rel(PROVISIONAL_REFS))

    if PENDING_MANIFEST.exists():
        manifest = _load(PENDING_MANIFEST)
        for case in manifest.get("cases") or []:
            match = next((a for a in ready if a["case_id"] == case["case_id"]), None)
            if match:
                case["publication_at"] = match["to_publication_at"]
                case["publication_at_basis"] = PDF_CONFIRMED_BASIS
        _write(PENDING_MANIFEST, manifest)
        wrote.append(_rel(PENDING_MANIFEST))

    if PENDING_SUMMARY.exists():
        summary = _load(PENDING_SUMMARY)
        for row in summary.get("results") or []:
            match = next((a for a in ready if a["case_id"] == row["case_id"]), None)
            if match:
                row["publication_at_basis"] = PDF_CONFIRMED_BASIS
                row["publication_at"] = match["to_publication_at"]
        _write(PENDING_SUMMARY, summary)
        wrote.append(_rel(PENDING_SUMMARY))

    if apply_shared_refs:
        shared = _load(SHARED_REFS)
        cases = shared["cases"] if isinstance(shared, dict) else shared
        by_shared = {c["case_id"]: c for c in cases}
        for action in ready:
            target = by_shared.get(action["case_id"])
            if target is None:
                continue
            target["publication_at"] = action["to_publication_at"]
            if action.get("publication_date"):
                target["publication_date"] = action["publication_date"]
        if isinstance(shared, dict):
            shared["note"] = (
                "publication_at filled from publisher PDF Stand-Uhr guesses; "
                "not exact exchange clock proof. Costco/BASF promoted from pending PDFs."
            )
            _write(SHARED_REFS, shared)
        else:
            _write(SHARED_REFS, cases)
        wrote.append(_rel(SHARED_REFS))

    return {"wrote": wrote, "promoted": [a["case_id"] for a in ready]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--provisional-refs", type=Path, default=PROVISIONAL_REFS)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write provisional overlay / manifest updates (default: dry-run)",
    )
    parser.add_argument(
        "--apply-shared-refs",
        action="store_true",
        help="Also fill reference-27-inputs-with-publication-at.json (requires --apply)",
    )
    parser.add_argument("--out", type=Path, help="Optional plan JSON path")
    args = parser.parse_args(argv)

    if args.apply_shared_refs and not args.apply:
        parser.error("--apply-shared-refs requires --apply")

    inventory = _load(args.inventory)
    provisional = _load(args.provisional_refs)
    plan = plan_promotions(inventory, provisional)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _write(args.out, plan)

    print(
        json.dumps({k: plan[k] for k in ("ready", "still_missing", "blocked", "actions")}, indent=2)
    )

    if not args.apply:
        print("dry-run; pass --apply to write")
        return 0

    result = apply_promotions(plan, apply_shared_refs=args.apply_shared_refs)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
