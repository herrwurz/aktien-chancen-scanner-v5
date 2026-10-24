"""Bounded GDELT DOC 2.0 metadata adapter."""

import hashlib
import json
from datetime import UTC, datetime

import httpx

from scanner.news import NewsBatch, NewsItem
from scanner.news_providers.cache import ImmutableNewsCache

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
POLICY = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"


def _timestamp(value):
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


class GdeltNewsSource:
    def __init__(
        self, root, *, allow_network=False, max_requests=0, client=None, clock=None, timeout=10
    ):
        if max_requests < 0 or not 1 <= timeout <= 30:
            raise ValueError("invalid GDELT request controls")
        self.cache = ImmutableNewsCache(root)
        self.allow_network = allow_network
        self.remaining = max_requests
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.timeout = timeout

    def fetch(self, query, *, start, end, limit, company_identifiers=None):
        if not 1 <= limit <= 250:
            raise ValueError("GDELT limit must be between 1 and 250")
        request = {
            "query": str(query),
            "startdatetime": start.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.astimezone(UTC).strftime("%Y%m%d%H%M%S"),
            "maxrecords": limit,
            "format": "json",
            "mode": "artlist",
        }
        cached = self.cache.read(request)
        cache_hit = cached is not None
        if cached:
            raw, manifest = cached
            retrieved = datetime.fromisoformat(manifest["retrieved_at"])
        else:
            if not self.allow_network or self.remaining <= 0:
                raise ValueError("explicit network authorization and request limit required")
            self.remaining -= 1
            client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=False)
            own = self.client is None
            try:
                response = client.get(
                    URL, params=request, timeout=self.timeout, follow_redirects=False
                )
                response.raise_for_status()
                raw = response.content
            except httpx.HTTPError as exc:
                raise ValueError("GDELT request failed") from exc
            finally:
                if own:
                    client.close()
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("GDELT response exceeds size limit")
            retrieved = self.clock()
            self.cache.write(
                request, raw, {"retrieved_at": retrieved.isoformat(), "policy": POLICY}
            )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("invalid GDELT JSON") from None
        items = []
        for row in payload.get("articles", [])[:limit]:
            published = _timestamp(row["seendate"])
            if not start <= published <= end:
                continue
            url, title = row.get("url"), row.get("title")
            if not url or not title:
                continue
            token = hashlib.sha256(f"{url}\n{published.isoformat()}".encode()).hexdigest()
            items.append(
                NewsItem(
                    source_id=f"gdelt:{token}",
                    source_type="SECONDARY",
                    url=url,
                    title=title,
                    published_at=published,
                    first_seen_at=retrieved,
                    retrieved_at=retrieved,
                    source_available_at=retrieved,
                    company_identifiers=company_identifiers or {},
                    event_type="news_mention",
                    event_confidence="unknown",
                    evidence_status="discovery_only",
                    license_status="metadata_only",
                    content_hash=hashlib.sha256(raw).hexdigest(),
                    origin_id=url,
                )
            )
        return NewsBatch(
            provider="GDELT_DOC_2",
            status="ok",
            items=items,
            retrieved_at=retrieved,
            cache_hit=cache_hit,
            request_count=0 if cache_hit else 1,
            coverage={
                "article_text_stored": False,
                "query": str(query),
                "license_scope": "metadata_only",
            },
        )
