"""Bounded GDELT DOC 2.0 metadata adapter."""

import hashlib
import json
import time
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
        self,
        root,
        *,
        allow_network=False,
        max_requests=0,
        max_retries=1,
        client=None,
        clock=None,
        sleeper=time.sleep,
        timeout=10,
    ):
        if max_requests < 0 or not 0 <= max_retries <= 2 or not 1 <= timeout <= 30:
            raise ValueError("invalid GDELT request controls")
        self.cache = ImmutableNewsCache(root)
        self.allow_network = allow_network
        self.remaining = max_requests
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_retries = max_retries
        self.sleep = sleeper
        self.timeout = timeout

    def fetch(
        self,
        query,
        *,
        start,
        end,
        limit,
        company_identifiers=None,
        identity_evidence_status=None,
    ):
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
            client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=False)
            own = self.client is None
            raw = None
            request_count = 0
            try:
                for attempt in range(self.max_retries + 1):
                    if self.remaining <= 0:
                        break
                    self.remaining -= 1
                    request_count += 1
                    try:
                        response = client.get(
                            URL, params=request, timeout=self.timeout, follow_redirects=False
                        )
                    except httpx.TransportError:
                        response = None
                    if response is not None and response.status_code == 200:
                        raw = response.content
                        break
                    retryable = response is None or response.status_code in {
                        429,
                        500,
                        502,
                        503,
                        504,
                    }
                    if not retryable:
                        break
                    if attempt < self.max_retries and self.remaining > 0:
                        self.sleep(min(2**attempt, 4))
            finally:
                if own:
                    client.close()
            if raw is None:
                return NewsBatch(
                    provider="GDELT_DOC_2",
                    status="unavailable",
                    retrieved_at=self.clock(),
                    request_count=request_count,
                    errors=["gdelt_retries_exhausted"],
                    coverage={"fallback_used": False, "configured": True},
                )
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
                    company_identifiers=(
                        company_identifiers or {}
                        if identity_evidence_status == "caller_verified"
                        else {}
                    ),
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
            request_count=0 if cache_hit else request_count,
            coverage={
                "article_text_stored": False,
                "query": str(query),
                "license_scope": "metadata_only",
                "identifier_attachment": (
                    "caller_verified" if identity_evidence_status == "caller_verified" else "none"
                ),
            },
        )
