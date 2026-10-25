"""Candidate source that merges index/fixture retrieval with EU universe and news."""

from __future__ import annotations

from datetime import timedelta

from scanner.research import AssetIdentity
from scanner.research_index.identity import stable_asset_id

from .eu_universe import filter_assets_by_clues, load_eu_dach_assets
from .news_channel import match_news_to_assets
from .retrieval import (
    CHANNEL_LIMIT,
    RetrievalCandidate,
    RetrievalReport,
    retrieve_candidates,
)


class HypothesisCandidateSource:
    """Stage-A source for usable top-3 hypotheses across EU curated + optional index/news."""

    source_id = "hypothesis-eu-dach-v1"

    def __init__(
        self,
        *,
        eu_assets=None,
        index=None,
        news_searcher=None,
        stage_a_limit=50,
        base_source=None,
    ):
        self.eu_assets = list(eu_assets if eu_assets is not None else load_eu_dach_assets())
        self.index = index
        self.news_searcher = news_searcher
        self.stage_a_limit = stage_a_limit
        self.base_source = base_source
        self._hits: list[RetrievalCandidate] = []
        self._point_in_time = None
        self._evidence = {stable_asset_id(asset): [] for asset in self.eu_assets}
        self.coverage = {
            "status": "not_searched",
            "kind": "hypothesis_eu_dach",
            "real_market_data": False,
            "eu_universe_size": len(self.eu_assets),
            "stage_a_limit": stage_a_limit,
            "channel_limit": CHANNEL_LIMIT,
            "not_covered_note": "Curated DACH/EU seed universe; not complete market coverage",
        }

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

        # Curated EU/DACH structural matches.
        for identity, score, reasons in filter_assets_by_clues(self.eu_assets, clues):
            add(
                identity,
                structured=score,
                ranks={"eu_sector": 1},
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
        stock_categories = {
            "sectors",
            "countries",
            "events",
            "fact_claims",
            "identifier",
            "business",
            "products",
            "technologies",
        }
        stock_clues = [
            clue
            for clue in clues
            if clue.instrument_scope == "stock" and clue.category in stock_categories
        ]
        if limited:
            status = "ok"
        elif index_report is not None and index_report.status != "ok":
            status = index_report.status
        elif not stock_clues and not search_queries:
            status = "insufficiently_constrained"
        else:
            status = "retrieval_missed"
        self.coverage.update(
            status=status,
            visible_universe_size=len(self.eu_assets)
            + (index_report.visible_universe_size if index_report else 0),
            full_universe_size=len(self.eu_assets)
            + (index_report.full_universe_size if index_report else 0),
            investigated_count=len(limited),
            matched_before_limit=len(candidates),
            channel_limit=CHANNEL_LIMIT,
            channel_counts={
                "eu_curated": len(filter_assets_by_clues(self.eu_assets, clues)),
                "news": len(news_hits),
                "index": len(index_report.candidates) if index_report else 0,
            },
            channel_matched_before_limit={
                "eu_curated": len(filter_assets_by_clues(self.eu_assets, clues)),
                "news": len(news_hits),
            },
            stage_a_asset_ids=[item.asset_id for item in limited],
            search_queries=search_queries,
            coverage_warnings=(index_report.coverage_warnings if index_report else []),
        )
        return RetrievalReport(
            status=status,
            candidates=limited,
            full_universe_size=self.coverage["full_universe_size"],
            visible_universe_size=self.coverage["visible_universe_size"],
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
        # Synthesize minimal sector/country evidence for curated EU identities.
        asset_id = stable_asset_id(identity)
        if asset_id not in {stable_asset_id(asset) for asset in self.eu_assets}:
            return []
        if self._point_in_time is None:
            return []
        available = identity.source_available_at or self._point_in_time
        facts = {}
        if identity.sector:
            facts["sectors"] = [identity.sector]
        if identity.country:
            facts["countries"] = [identity.country]
        payload = {
            "source_id": f"eu-identity:{asset_id}",
            "url": f"fixture://eu-dach/{asset_id}",
            "title": f"Curated identity card for {identity.name}",
            "published_at": available.isoformat(),
            "retrieved_at": available.isoformat(),
            "effective_at": available.isoformat(),
            "source_available_at": available.isoformat(),
            "source_kind": "regulatory",
            "facts": {**facts, "origin_id": f"eu-identity:{asset_id}"},
            "content_sha256": "e" * 64,
        }
        return [payload]
