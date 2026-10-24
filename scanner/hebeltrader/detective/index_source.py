"""Stage-A research-index adapter for the existing detective Stage-B ranking."""

from scanner.research_index.models import CandidateQuery


class IndexCandidateSource:
    source_id = "sqlite-fts5-research-index"

    def __init__(self, index, *, stage_a_limit=50):
        self.index = index
        self.stage_a_limit = stage_a_limit
        self._hits = []
        self.coverage = {
            "status": "not_searched",
            "kind": "real_archived_index",
            "stage_a_limit": stage_a_limit,
        }

    def search_candidates(self, text, clues, point_in_time):
        if point_in_time is None:
            self._hits = []
            self.coverage.update(status="unavailable", error_code="publication_time_required")
            return
        query = CandidateQuery(
            sectors=clues["structured"]["sectors"],
            countries=clues["structured"]["countries"],
            event_types=clues["structured"]["events"],
            fact_claims=clues["structured"]["fact_claims"],
        )
        result = self.index.candidates(query, as_of=point_in_time, limit=self.stage_a_limit)
        self._hits = result.candidates
        self.coverage.update(
            status=result.status,
            full_universe_size=result.full_universe_size,
            visible_universe_size=result.visible_universe_size,
            investigated_count=len(result.candidates),
            matched_before_limit=result.matched_before_limit,
            index_payload_sha256=result.index_payload_sha256,
        )

    def load_candidates(self):
        return [
            {
                "identity": hit.identity.model_dump(mode="json"),
                "aliases": [value for value in (hit.identity.name, hit.identity.ticker) if value],
            }
            for hit in self._hits
        ]

    def evidence_for(self, identity):
        return []
