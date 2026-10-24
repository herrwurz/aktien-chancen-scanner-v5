"""Failure-isolating orchestration for bounded news providers."""

from scanner.news import NewsBatch
from scanner.news_cluster import cluster_news


class NewsCollector:
    def __init__(self, sources):
        self.sources = list(sources)

    def collect(self, query, *, start, end, limit, as_of, max_age_days):
        batches, errors = [], []
        for position, source in enumerate(self.sources, start=1):
            try:
                batch = source.fetch(query, start=start, end=end, limit=limit)
            except (OSError, TypeError, ValueError):
                errors.append(f"provider_{position}_failed")
                continue
            batches.append(batch)
            if batch.status == "unavailable":
                errors.extend(batch.errors or [f"provider_{position}_unavailable"])

        successful = [row for row in batches if row.status in {"ok", "partial"}]
        freshness = [row.freshness(as_of=as_of, max_age_days=max_age_days) for row in successful]
        clusters = cluster_news([item for batch in successful for item in batch.items])
        priority = {"PRIMARY": 3, "SECONDARY": 2, "COMMUNITY": 1}
        items = [
            max(cluster.items, key=lambda row: (priority[row.source_type], row.source_id))
            for cluster in clusters
        ][:limit]
        unavailable = len(self.sources) - len(successful)
        status = (
            "ok" if successful and not unavailable else "partial" if successful else "unavailable"
        )
        return NewsBatch(
            provider="NEWS_COLLECTOR",
            status=status,
            items=items,
            retrieved_at=max((row.retrieved_at for row in batches), default=as_of),
            request_count=sum(row.request_count for row in batches),
            cost_eur=sum(row.cost_eur for row in batches),
            errors=errors,
            coverage={
                "configured_sources": len(self.sources),
                "successful_sources": len(successful),
                "unavailable_sources": unavailable,
                "fresh_sources": sum(row["status"] == "fresh" for row in freshness),
                "stale_sources": sum(row["status"] == "stale" for row in freshness),
                "event_clusters": len(clusters),
            },
        )
