"""Map news/search hits onto the curated company universe for Stage A."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from scanner.research import AssetIdentity
from scanner.research_index.identity import stable_asset_id


@dataclass(frozen=True)
class NewsHit:
    title: str
    url: str
    published_at: datetime | None = None
    source_id: str = "news"


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def match_news_to_assets(
    hits: list[NewsHit],
    assets: list[AssetIdentity],
    *,
    limit: int = 50,
) -> list[tuple[AssetIdentity, int, list[str]]]:
    """Score assets by name/ticker mentions in news titles."""
    scored: dict[str, dict] = {}
    for asset in assets:
        needles = [
            _normalize(asset.name),
            _normalize(asset.ticker or ""),
            _normalize((asset.name or "").split()[0]),
        ]
        needles = [item for item in needles if len(item) >= 3]
        for hit in hits:
            haystack = _normalize(hit.title)
            if not haystack:
                continue
            if any(needle and needle in haystack for needle in needles):
                asset_id = stable_asset_id(asset)
                row = scored.setdefault(asset_id, {"identity": asset, "score": 0, "reasons": []})
                row["score"] += 35
                row["reasons"].append(f"news:{hit.source_id}:{hit.title[:80]}")
    ranked = sorted(
        ((row["identity"], row["score"], row["reasons"]) for row in scored.values()),
        key=lambda item: (-item[1], item[0].name),
    )
    return ranked[:limit]


class FixtureNewsSearcher:
    """Offline news corpus for deterministic hypothesis tests."""

    def __init__(self, rows: list[dict]):
        self.rows = rows

    def search(self, queries: list[str], *, start: datetime, end: datetime, limit: int = 50):
        hits = []
        query_blob = " ".join(queries).casefold()
        for row in self.rows:
            title = row["title"]
            tokens = [
                token for token in re.findall(r"[a-z0-9äöüß]+", title.casefold()) if len(token) > 3
            ]
            if query_blob and not any(token in query_blob for token in tokens):
                # Keep logistics/takeover fixture rows when queries mention those themes.
                themes = row.get("themes", [])
                if not any(theme in query_blob for theme in themes):
                    continue
            published = datetime.fromisoformat(row["published_at"])
            if published < start or published > end:
                continue
            hits.append(
                NewsHit(
                    title=title,
                    url=row.get("url", "fixture://news"),
                    published_at=published,
                    source_id=row.get("source_id", "fixture-news"),
                )
            )
            if len(hits) >= limit:
                break
        return hits


class GdeltNewsSearcher:
    """Thin adapter over GdeltNewsSource.fetch for hypothesis queries."""

    def __init__(self, source):
        self.source = source

    def search(self, queries: list[str], *, start: datetime, end: datetime, limit: int = 50):
        hits = []
        for query in queries[:4]:
            batch = self.source.fetch(query, start=start, end=end, limit=min(limit, 50))
            for item in batch.items:
                hits.append(
                    NewsHit(
                        title=item.title,
                        url=item.url,
                        published_at=item.published_at,
                        source_id="gdelt",
                    )
                )
        return hits[:limit]
