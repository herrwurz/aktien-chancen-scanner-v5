"""Dry-run / promote behaviour for pending PDF publication_at overlays."""

from __future__ import annotations

import json

from scripts.promote_provisional_publication_at import (
    PDF_CONFIRMED_BASIS,
    apply_promotions,
    plan_promotions,
)


def _provisional():
    return {
        "schema_version": 1,
        "note": "test",
        "cases": [
            {
                "case_id": "HT-003",
                "publication_date": "2026-10-16",
                "publication_at": "2026-10-16T08:15:00+01:00",
                "publication_at_basis": "featured_date_plus_corpus_stand_0815_pdf_pending",
                "featured_issue": "192/26",
            },
            {
                "case_id": "HT-012",
                "publication_date": "2026-07-31",
                "publication_at": "2026-07-31T08:15:00+01:00",
                "publication_at_basis": "featured_date_plus_corpus_stand_0815_pdf_pending",
                "featured_issue": "137/26",
            },
        ],
    }


def test_plan_reports_missing_without_dropped_ht016():
    inventory = {"pdfs": []}
    plan = plan_promotions(inventory, _provisional())
    assert plan["ready"] == 0
    assert plan["still_missing"] == 2
    assert plan["blocked"] == []
    statuses = {a["case_id"]: a["status"] for a in plan["actions"]}
    assert statuses["HT-003"] == "still_missing_pdf"
    assert statuses["HT-012"] == "still_missing_pdf"


def test_plan_ready_when_stand_guess_present():
    inventory = {
        "pdfs": [
            {
                "issue": "192/26",
                "filename": "Hebeltrader_2026-192_Costco_abcd.pdf",
                "label_hint": "Costco",
                "publication_date": "2026-10-16",
                "publication_at_guess": "2026-10-16T08:17:00+01:00",
            }
        ]
    }
    plan = plan_promotions(inventory, _provisional())
    by_id = {a["case_id"]: a for a in plan["actions"]}
    assert by_id["HT-003"]["status"] == "ready_to_promote"
    assert by_id["HT-003"]["to_publication_at"] == "2026-10-16T08:17:00+01:00"
    assert by_id["HT-012"]["status"] == "still_missing_pdf"
    assert plan["ready"] == 1


def test_apply_promotions_updates_overlay(tmp_path, monkeypatch):
    import scripts.promote_provisional_publication_at as mod

    provisional_path = tmp_path / "refs.json"
    provisional_path.write_text(json.dumps(_provisional()), encoding="utf-8")
    monkeypatch.setattr(mod, "PROVISIONAL_REFS", provisional_path)
    monkeypatch.setattr(mod, "PENDING_MANIFEST", tmp_path / "missing-manifest.json")
    monkeypatch.setattr(mod, "PENDING_SUMMARY", tmp_path / "missing-summary.json")
    monkeypatch.setattr(mod, "SHARED_REFS", tmp_path / "shared.json")

    plan = {
        "recorded_at": "2026-10-31T12:00:00+00:00",
        "actions": [
            {
                "case_id": "HT-003",
                "status": "ready_to_promote",
                "to_publication_at": "2026-10-16T08:17:00+01:00",
                "publication_date": "2026-10-16",
                "filename": "Hebeltrader_2026-192_Costco_abcd.pdf",
            }
        ],
    }
    result = apply_promotions(plan, apply_shared_refs=False)
    assert result["promoted"] == ["HT-003"]
    updated = json.loads(provisional_path.read_text(encoding="utf-8"))
    case = next(c for c in updated["cases"] if c["case_id"] == "HT-003")
    assert case["publication_at"] == "2026-10-16T08:17:00+01:00"
    assert case["publication_at_basis"] == PDF_CONFIRMED_BASIS
    assert case["promoted_from_pdf"].endswith("Costco_abcd.pdf")
