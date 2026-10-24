"""Explicitly allowlisted issuer RSS/Atom metadata adapter."""

import hashlib
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, HttpUrl, model_validator

from scanner.news import NewsBatch, NewsItem
from scanner.news_providers.cache import ImmutableNewsCache


class IssuerFeedConfig(BaseModel):
    url: HttpUrl
    issuer_name: str
    company_identifiers: dict[str, list[str]]
    license_status: str
    license_reference: str

    @model_validator(mode="after")
    def permitted(self):
        if self.license_status != "permitted_metadata" or not self.license_reference:
            raise ValueError("feed license must explicitly permit metadata use")
        if not any(self.company_identifiers.values()):
            raise ValueError("issuer identifier evidence required")
        return self


class IssuerFeedNewsSource:
    def __init__(
        self,
        configs,
        root,
        *,
        allow_network=False,
        max_requests=0,
        client=None,
        clock=None,
        timeout=10,
    ):
        self.configs = list(configs)
        self.cache = ImmutableNewsCache(root)
        self.allow_network = allow_network
        self.remaining = max_requests
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.timeout = timeout

    def fetch(self, query, *, start, end, limit, **kwargs):
        matches = [row for row in self.configs if query.casefold() in row.issuer_name.casefold()]
        if not matches:
            return NewsBatch(
                provider="ISSUER_FEED",
                status="unavailable",
                retrieved_at=self.clock(),
                errors=["feed_not_allowlisted"],
            )
        items, retrieved, request_count, cache_hits = [], self.clock(), 0, 0
        for config in matches:
            request = {"url": str(config.url), "provider": "ISSUER_FEED"}
            cached = self.cache.read(request)
            if cached:
                raw, manifest = cached
                retrieved = datetime.fromisoformat(manifest["retrieved_at"])
                cache_hits += 1
            else:
                if not self.allow_network or self.remaining <= 0:
                    raise ValueError("explicit network authorization and request limit required")
                self.remaining -= 1
                request_count += 1
                client = self.client or httpx.Client(timeout=self.timeout, follow_redirects=False)
                own = self.client is None
                try:
                    try:
                        response = client.get(
                            str(config.url), timeout=self.timeout, follow_redirects=False
                        )
                        response.raise_for_status()
                        raw = response.content
                    except httpx.HTTPError:
                        return NewsBatch(
                            provider="ISSUER_FEED",
                            status="unavailable",
                            retrieved_at=self.clock(),
                            request_count=request_count,
                            errors=["issuer_feed_request_failed"],
                            coverage={"allowlisted_feeds": len(matches)},
                        )
                finally:
                    if own:
                        client.close()
                retrieved = self.clock()
                self.cache.write(
                    request,
                    raw,
                    {
                        "retrieved_at": retrieved.isoformat(),
                        "license_reference": config.license_reference,
                    },
                )
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("issuer feed exceeds size limit")
            lowered = raw.lower()
            if b"<!doctype" in lowered or b"<!entity" in lowered:
                raise ValueError("unsafe XML declaration in issuer feed")
            try:
                root = ElementTree.fromstring(raw)
            except ElementTree.ParseError:
                raise ValueError("invalid issuer feed XML") from None
            for entry in list(root.findall(".//item")) + list(root.findall(".//{*}entry")):
                title = entry.findtext("title") or entry.findtext("{*}title")
                link = entry.findtext("link")
                if link is None:
                    node = entry.find("{*}link")
                    link = node.get("href") if node is not None else None
                published_text = (
                    entry.findtext("pubDate")
                    or entry.findtext("{*}published")
                    or entry.findtext("{*}updated")
                )
                guid = entry.findtext("guid") or entry.findtext("{*}id") or link
                if not title or not link or not published_text or not guid:
                    continue
                try:
                    published = parsedate_to_datetime(published_text)
                except (TypeError, ValueError):
                    published = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
                if published.tzinfo is None:
                    published = published.replace(tzinfo=UTC)
                if not start <= published <= end:
                    continue
                items.append(
                    NewsItem(
                        source_id=f"issuer-feed:{hashlib.sha256(str(guid).encode()).hexdigest()}",
                        source_type="PRIMARY",
                        url=link,
                        title=title,
                        published_at=published,
                        first_seen_at=retrieved,
                        retrieved_at=retrieved,
                        source_available_at=retrieved,
                        company_identifiers=config.company_identifiers,
                        event_type="issuer_announcement",
                        event_confidence="source_claim",
                        evidence_status="issuer_publication",
                        license_status="permitted_metadata",
                        content_hash=hashlib.sha256(raw).hexdigest(),
                        origin_id=str(guid),
                    )
                )
        return NewsBatch(
            provider="ISSUER_FEED",
            status="ok",
            items=items[:limit],
            retrieved_at=retrieved,
            cache_hit=cache_hits == len(matches),
            request_count=request_count,
            coverage={"allowlisted_feeds": len(matches)},
        )
