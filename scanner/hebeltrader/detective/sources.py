from copy import deepcopy
from typing import Protocol


class CandidateSource(Protocol):
    source_id: str
    coverage: dict

    def load_candidates(self): ...


class NewsEvidenceSource(Protocol):
    source_id: str

    def evidence_for(self, identity): ...


class OfflineFixtureSource:
    """Deterministic test/bootstrap source; explicitly not general market coverage."""

    source_id = "offline-fixture-universe-v2"

    def __init__(self, candidates):
        self._candidates = candidates
        self.coverage = {
            "status": "fixture_limited",
            "kind": "synthetic_fixture",
            "real_market_data": False,
            "candidate_count": len(candidates),
            "markets": ["DE", "US"],
            "general_market_coverage": False,
            "blocker": (
                "No budget-compatible, licensed point-in-time company/news universe is "
                "configured. Out-of-universe teasers must abstain."
            ),
        }

    def load_candidates(self):
        return deepcopy(self._candidates)

    def evidence_for(self, identity):
        for candidate in self._candidates:
            if candidate["identity"].get("wkn") == identity.wkn:
                return deepcopy(candidate.get("evidence", []))
        return []


class UnavailableResearchSource:
    source_id = "research-unavailable"

    def __init__(self, error_code):
        self.coverage = {
            "status": "unavailable",
            "kind": "real_research",
            "real_market_data": False,
            "error_code": error_code,
            "candidate_count": 0,
        }

    def load_candidates(self):
        return []

    def evidence_for(self, identity):
        return []
