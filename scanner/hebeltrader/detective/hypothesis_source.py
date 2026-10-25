"""Candidate source that merges index/fixture retrieval with EU universe and news."""

from __future__ import annotations

from datetime import timedelta

from scanner.research import AssetIdentity
from scanner.research_index.identity import stable_asset_id

from .eu_universe import filter_assets_by_clues, load_curated_hypothesis_assets
from .news_channel import match_news_to_assets
from .retrieval import (
    CHANNEL_LIMIT,
    RetrievalCandidate,
    RetrievalReport,
    retrieve_candidates,
)

_BASE_COVERAGE_KEYS = (
    "kind",
    "status",
    "real_market_data",
    "universe_total",
    "data_age_seconds",
    "generated_at",
    "candidate_count",
    "markets",
    "general_market_coverage",
    "blocker",
    "error_code",
    "sampling_strategy",
    "search_scope",
    "full_universe_size",
    "listing_count",
    "investigated_count",
    "coverage_ratio",
    "sector_available_count",
    "missing_sector_rate",
    "company_metrics_available_count",
    "company_metrics_coverage_ratio",
    "recall_unmeasurable",
    "not_covered_markets",
    "requests_attempted",
    "cost_eur",
)


class HypothesisCandidateSource:
    """Stage-A source for usable top-3 hypotheses across curated EU/US + optional index/news."""

    source_id = "hypothesis-curated-v1"

    def __init__(
        self,
        *,
        eu_assets=None,
        index=None,
        news_searcher=None,
        stage_a_limit=50,
        base_source=None,
    ):
        # Parameter name kept for callers; payload is the merged curated hypothesis universe.
        self.eu_assets = list(
            eu_assets if eu_assets is not None else load_curated_hypothesis_assets()
        )
        self.index = index
        self.news_searcher = news_searcher
        self.stage_a_limit = stage_a_limit
        self.base_source = base_source
        self._hits: list[RetrievalCandidate] = []
        self._point_in_time = None
        self._evidence = {stable_asset_id(asset): [] for asset in self.eu_assets}
        self.coverage = {
            "status": "not_searched",
            "kind": "hypothesis_curated_eu_us",
            "real_market_data": False,
            "eu_universe_size": len(self.eu_assets),
            "curated_universe_size": len(self.eu_assets),
            "stage_a_limit": stage_a_limit,
            "channel_limit": CHANNEL_LIMIT,
            "not_covered_note": (
                "Curated EU/DACH + US seed universe; not complete market coverage"
            ),
        }
        self._overlay_base_coverage()

    def _overlay_base_coverage(self):
        if self.base_source is None:
            return
        base_cov = getattr(self.base_source, "coverage", None) or {}
        for key in _BASE_COVERAGE_KEYS:
            if key in base_cov:
                self.coverage[key] = base_cov[key]

    def _ingest_base_catalog(self, add, clues):
        """Warm live/cached/fixture bases and fold their identities into Stage A."""
        if self.base_source is None:
            return 0
        if hasattr(self.base_source, "retrieve_candidates") and self.index is None:
            report = self.base_source.retrieve_candidates(clues, self._point_in_time)
            for rank, hit in enumerate(report.candidates, 1):
                add(
                    hit.identity,
                    rrf=hit.rrf_score,
                    structured=hit.structured_score,
                    ranks={**hit.channel_ranks, "base": rank},
                    uncertainties=hit.uncertainties,
                    reasons=[f"base_rank:{rank}"],
                )
            self._overlay_base_coverage()
            return len(report.candidates)
        if not hasattr(self.base_source, "load_candidates"):
            return 0
        rows = self.base_source.load_candidates()
        self._overlay_base_coverage()
        count = 0
        for rank, raw in enumerate(rows, 1):
            identity = AssetIdentity.model_validate(raw["identity"])
            facts = {}
            for evidence in raw.get("evidence") or []:
                for key, value in (evidence.get("facts") or {}).items():
                    if isinstance(value, list):
                        facts.setdefault(key, [])
                        facts[key].extend(value)
            score = 5
            reasons = ["base_catalog"]
            clue_sectors = {
                clue.value or clue.normalized
                for clue in clues
                if clue.category == "sectors" and clue.instrument_scope == "stock"
            }
            clue_countries = {
                clue.value or clue.normalized
                for clue in clues
                if clue.category == "countries" and clue.instrument_scope == "stock"
            }
            overlap = clue_sectors & set(facts.get("sectors") or [])
            if overlap:
                score += 40
                reasons.append(f"sector:{sorted(overlap)[0]}")
            country_overlap = clue_countries & set(facts.get("countries") or [])
            if country_overlap:
                score += 20
                reasons.append(f"country:{sorted(country_overlap)[0]}")
            add(
                identity,
                structured=score,
                ranks={"base_catalog": rank},
                reasons=reasons,
            )
            count += 1
        return count

    def retrieve_candidates(self, clues, point_in_time, *, search_queries=None):
        search_queries = search_queries or []
        self._point_in_time = point_in_time
        records: dict[str, dict] = {}

        def add(identity, *, rrf=0, structured=0, ranks=None, reasons=None, uncertainties=None):
            asset_id = stable_asset_id(identity)
            row = records.setdefault(
                asset_id,
                {
                    "identity": identity,
                    "rrf": 0,
                    "structured": 0,
                    "ranks": {},
                    "reasons": [],
                    "uncertainties": [],
                },
            )
            row["rrf"] += rrf
            row["structured"] += structured
            row["ranks"].update(ranks or {})
            row["reasons"].extend(reasons or [])
            row["uncertainties"].extend(uncertainties or [])

        base_count = self._ingest_base_catalog(add, clues)

        # Curated EU/DACH + US seed structural matches (point-in-time filtered).
        eu_matches = filter_assets_by_clues(self.eu_assets, clues, as_of=point_in_time)
        for identity, score, reasons in eu_matches:
            add(
                identity,
                structured=score,
                ranks={"curated_sector": 1, "eu_sector": 1},
                reasons=reasons,
            )

        # Optional full research index.
        index_report = None
        if self.index is not None:
            index_report = retrieve_candidates(
                self.index, clues, as_of=point_in_time, limit=self.stage_a_limit
            )
            for rank, hit in enumerate(index_report.candidates, 1):
                add(
                    hit.identity,
                    rrf=hit.rrf_score,
                    structured=hit.structured_score,
                    ranks={**hit.channel_ranks, "index": rank},
                    uncertainties=hit.uncertainties,
                    reasons=[f"index_rank:{rank}"],
                )

        # News/query channel.
        news_hits = []
        if self.news_searcher is not None and search_queries:
            start = point_in_time - timedelta(days=30)
            end = point_in_time
            news_hits = self.news_searcher.search(
                search_queries, start=start, end=end, limit=CHANNEL_LIMIT
            )
            for identity, score, reasons in match_news_to_assets(
                news_hits, self.eu_assets, limit=CHANNEL_LIMIT
            ):
                add(
                    identity,
                    structured=score,
                    ranks={"news": 1},
                    reasons=reasons,
                )

        candidates = []
        for asset_id, row in records.items():
            identity = row["identity"]
            if identity.asset_type != "stock" or identity.instrument_type in {"fund", "other"}:
                continue
            total = row["rrf"] + row["structured"]
            candidates.append(
                RetrievalCandidate(
                    asset_id=asset_id,
                    identity=identity,
                    rrf_score=row["rrf"],
                    structured_score=row["structured"],
                    total_score=total,
                    channel_ranks=row["ranks"],
                    uncertainties=sorted(set(row["uncertainties"] + row["reasons"]))[:12],
                )
            )
        candidates.sort(key=lambda item: (-item.total_score, item.asset_id))
        limited = candidates[: self.stage_a_limit]
        self._hits = limited
        # Events/earnings alone are too weak; require sector/geo/identity constraints.
        hard_categories = {
            "sectors",
            "countries",
            "identifier",
            "business",
            "products",
            "technologies",
        }
        hard_clues = [
            clue
            for clue in clues
            if clue.instrument_scope == "stock" and clue.category in hard_categories
        ]
        if limited and hard_clues:
            status = "ok"
        elif not hard_clues:
            status = "insufficiently_constrained"
            limited = []
            self._hits = []
            candidates = []
        elif index_report is not None and index_report.status != "ok":
            status = index_report.status
        else:
            status = "retrieval_missed"

        if index_report is not None:
            full_universe = index_report.full_universe_size
            visible_universe = index_report.visible_universe_size
        elif self.base_source is not None and "universe_total" in (
            getattr(self.base_source, "coverage", {}) or {}
        ):
            full_universe = self.base_source.coverage["universe_total"]
            visible_universe = self.base_source.coverage.get("investigated_count", full_universe)
        elif self.base_source is not None and "candidate_count" in (
            getattr(self.base_source, "coverage", {}) or {}
        ):
            full_universe = self.base_source.coverage["candidate_count"]
            visible_universe = full_universe
        else:
            full_universe = len(self.eu_assets)
            visible_universe = len(self.eu_assets)

        self.coverage.update(
            visible_universe_size=visible_universe,
            full_universe_size=full_universe,
            eu_universe_size=len(self.eu_assets),
            investigated_count=len(limited),
            matched_before_limit=len(candidates),
            channel_limit=CHANNEL_LIMIT,
            channel_counts={
                "curated": len(eu_matches),
                "eu_curated": len(eu_matches),
                "news": len(news_hits),
                "index": len(index_report.candidates) if index_report else 0,
                "base_catalog": base_count,
            },
            channel_matched_before_limit={
                "curated": len(eu_matches),
                "eu_curated": len(eu_matches),
                "news": len(news_hits),
                "base_catalog": base_count,
            },
            stage_a_asset_ids=[item.asset_id for item in limited],
            search_queries=search_queries,
            coverage_warnings=(index_report.coverage_warnings if index_report else []),
        )
        # Preserve authoritative base labels (fixture_limited / real_archived / …).
        self._overlay_base_coverage()
        if "status" not in (getattr(self.base_source, "coverage", {}) or {}):
            self.coverage["status"] = status
        return RetrievalReport(
            status=status,
            candidates=limited,
            full_universe_size=full_universe,
            visible_universe_size=visible_universe,
            matched_before_limit=len(candidates),
            channel_limit=CHANNEL_LIMIT,
            channel_counts=self.coverage["channel_counts"],
            channel_matched_before_limit=self.coverage["channel_matched_before_limit"],
            coverage_warnings=list(self.coverage.get("coverage_warnings") or []),
        )

    def load_candidates(self):
        return [
            {
                "identity": hit.identity.model_dump(mode="json"),
                "aliases": [value for value in (hit.identity.name, hit.identity.ticker) if value],
            }
            for hit in self._hits
        ]

    def evidence_for(self, identity: AssetIdentity):
        if self.base_source is not None:
            rows = self.base_source.evidence_for(identity)
            if rows:
                return rows
        # Synthesize minimal sector/country evidence for curated seed identities.
        asset_id = stable_asset_id(identity)
        if asset_id not in {stable_asset_id(asset) for asset in self.eu_assets}:
            return []
        if self._point_in_time is None:
            return []
        if not identity.historically_available_at(self._point_in_time):
            return []
        available = identity.source_available_at or self._point_in_time
        facts = {}
        if identity.sector:
            facts["sectors"] = [identity.sector]
        if identity.country:
            facts["countries"] = [identity.country]
        origin = identity.source_id or "curated-identity"
        payload = {
            "source_id": f"{origin}:{asset_id}",
            "url": f"fixture://curated/{asset_id}",
            "title": f"Curated identity card for {identity.name}",
            "published_at": available.isoformat(),
            "retrieved_at": available.isoformat(),
            "effective_at": available.isoformat(),
            "source_available_at": available.isoformat(),
            "source_kind": "regulatory",
            "facts": {**facts, "origin_id": f"{origin}:{asset_id}"},
            "content_sha256": "e" * 64,
        }
        return [payload]
