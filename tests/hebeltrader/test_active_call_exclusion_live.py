"""Live Investigator respects the 180-day active-call exclusion blocklist."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from scanner.hebeltrader.detective.featured_calls import blocked_features
from scanner.hebeltrader.detective.investigation import (
    InvestigationRequest,
    Investigator,
    _filter_active_call_blocked,
    _query_targets_blocked,
)

NOW = datetime(2026, 10, 30, 8, 15, tzinfo=UTC)

FEATURED = {
    "kind": "hebeltrader_featured_calls_blocklist",
    "default_lookback_days": 180,
    "calls": [
        {
            "company": "Analog Devices",
            "ticker": "ADI",
            "featured_date": "2026-10-28",
            "featured_issue": "200/26",
            "source_case_id": "HT-001",
        },
        {
            "company": "NXP Semiconductors",
            "ticker": "NXPI",
            "featured_date": "2026-09-01",
            "featured_issue": "160/26",
            "source_case_id": "HT-X",
        },
    ],
}


class StubWeb:
    phase = "input"

    def __init__(self):
        self.apis = SimpleNamespace(
            ai_key="k",
            search_calls=0,
            ai_calls=0,
            budget=SimpleNamespace(summary=lambda: {}),
            plan=lambda text: {
                "clues": [],
                "candidate_hypotheses": [
                    "Analog Devices",
                    "NXP Semiconductors",
                    "Texas Instruments",
                ],
                "queries": [
                    '"Analog Devices" sole supplier market share monopoly',
                    '"Texas Instruments" sole supplier market share monopoly',
                ],
            },
            review_candidates=lambda rows: {
                "status": "ok",
                "changes_deterministic_ranking": False,
            },
        )
        self.queries = []

    def set_phase(self, phase):
        self.phase = phase

    def search(self, query, limit=10):
        self.queries.append(query)
        return []

    def fetch_many(self, urls):
        return [], []


def test_filter_drops_blocked_ranked_rows():
    blocked = blocked_features("2026-10-30", lookback_days=180, featured=FEATURED)
    ranked = [
        {
            "asset_id": "a",
            "identity": {"name": "Analog Devices", "ticker": "ADI"},
            "evidence_score": 9,
        },
        {
            "asset_id": "b",
            "identity": {"name": "Texas Instruments", "ticker": "TXN"},
            "evidence_score": 3,
        },
    ]
    kept, dropped = _filter_active_call_blocked(ranked, blocked)
    assert [r["asset_id"] for r in kept] == ["b"]
    assert dropped[0]["ticker"] == "ADI"
    assert dropped[0]["reason"] == "active_call_exclusion_180d"


def test_query_targets_blocked_detects_quoted_names():
    blocked = blocked_features("2026-10-30", lookback_days=180, featured=FEATURED)
    assert _query_targets_blocked('"Analog Devices" earnings', blocked)
    assert not _query_targets_blocked('"Texas Instruments" earnings', blocked)


def test_live_planner_drops_blocked_verification_queries(tmp_path, monkeypatch):
    from scanner.hebeltrader.detective import featured_calls as fc

    monkeypatch.setattr(fc, "load_featured_calls", lambda path=None: FEATURED)
    web = StubWeb()
    report = Investigator(tmp_path, web=web, clock=lambda: NOW).analyze(
        InvestigationRequest(
            teaser_text=(
                "Der heimliche Herrscher über die globale Chipindustrie! "
                "Kunden haben kaum noch eine Wahl."
            ),
            publication_at=NOW,
        )
    )
    excl = report["active_call_exclusion"]
    assert excl["status"] == "ok"
    assert excl["blocklist_entries"] >= 2
    blob = " ".join(report["search_queries"])
    assert "Analog Devices" not in blob
    assert "Texas Instruments" in blob or "semiconductor" in blob.lower()
