"""Stage-A research-index adapter for the existing detective Stage-B ranking."""

from scanner.research_index.models import CandidateQuery

from .retrieval import retrieve_candidates


class IndexCandidateSource:
    source_id = "sqlite-fts5-research-index"

    def __init__(self, index, *, stage_a_limit=50):
        self.index = index
        self.stage_a_limit = stage_a_limit
        self._hits = []
        self._point_in_time = None
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
        self._point_in_time = point_in_time
        self._hits = result.candidates
        self.coverage.update(
            status=result.status,
            full_universe_size=result.full_universe_size,
            visible_universe_size=result.visible_universe_size,
            investigated_count=len(result.candidates),
            matched_before_limit=result.matched_before_limit,
            index_payload_sha256=result.index_payload_sha256,
        )

    def retrieve_candidates(self, clues, point_in_time):
        if point_in_time is None:
            self._hits = []
            self.coverage.update(status="unavailable", error_code="publication_time_required")
            return None
        report = retrieve_candidates(
            self.index, clues, as_of=point_in_time, limit=self.stage_a_limit
        )
        self._point_in_time = point_in_time
        self._hits = report.candidates
        self.coverage.update(
            status=report.status,
            full_universe_size=report.full_universe_size,
            visible_universe_size=report.visible_universe_size,
            investigated_count=len(report.candidates),
            matched_before_limit=report.matched_before_limit,
            channel_limit=report.channel_limit,
            index_payload_sha256=report.index_payload_sha256,
            channel_counts=report.channel_counts,
            channel_matched_before_limit=report.channel_matched_before_limit,
            coverage_warnings=report.coverage_warnings,
            exclusions=[item.model_dump(mode="json") for item in report.exclusions],
            stage_a_asset_ids=[item.asset_id for item in report.candidates],
        )
        return report

    def load_candidates(self):
        return [
            {
                "identity": hit.identity.model_dump(mode="json"),
                "aliases": [value for value in (hit.identity.name, hit.identity.ticker) if value],
            }
            for hit in self._hits
        ]

    def evidence_for(self, identity):
        if self._point_in_time is None:
            return []
        return self.index.detective_evidence(identity, as_of=self._point_in_time)
