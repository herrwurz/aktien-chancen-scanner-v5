"""Bounded, opt-in public research. Search results are hints, never page evidence."""

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from uuid import uuid4
from xml.etree import ElementTree

import httpx


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self.meta, self.ld = [], [], {}, []
        self.hidden = 0
        self.in_title = False
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
            if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
                self.script = []
        if tag == "meta":
            self.meta[(attrs.get("property") or attrs.get("name") or "").lower()] = attrs.get(
                "content", ""
            )

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
            if tag == "script" and self.script is not None:
                try:
                    self.ld.append(json.loads("".join(self.script)))
                except (ValueError, TypeError):
                    pass
                self.script = None

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if self.in_title:
            self.title.append(data)
        if not self.hidden:
            self.parts.append(data)


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return dt.isoformat() if dt.tzinfo is not None else None


def parse_page(raw, url, *, retrieved_at=None, raw_file="", primary_domains=None):
    """Parse explicit metadata only; missing identity/date is intentionally unknown."""
    p = _Page()
    p.feed(raw.decode("utf-8", errors="replace"))
    host = (urlsplit(url).hostname or "").lower()
    approved = primary_domains or {}
    name = approved.get(host)
    kind = (
        "regulatory"
        if host == "sec.gov" or host.endswith(".sec.gov")
        else "issuer"
        if name
        else "news"
    )
    published = _date(p.meta.get("article:published_time") or p.meta.get("datepublished"))
    ticker = None
    for key, value in p.meta.items():
        if (
            key in ("isaccessibleforfree", "is_accessible_for_free")
            and value.lower() in ("false", "0")
        ) or (
            any(marker in key for marker in ("paywall", "login_required", "requires_login"))
            and value.lower() not in ("", "false", "0", "none")
        ):
            raise ValueError("paywall or login metadata denies public extraction")

    def walk(obj, identity=False):
        nonlocal name, ticker, published
        if isinstance(obj, list):
            for item in obj:
                walk(item, identity)
        elif isinstance(obj, dict):
            if (
                obj.get("isAccessibleForFree") is False
                or str(obj.get("isAccessibleForFree", "")).lower() == "false"
            ):
                raise ValueError("paywall metadata denies public extraction")
            if identity and obj.get("@type") in ("Organization", "Corporation", "PublicCompany"):
                name = name or obj.get("name")
                ticker = ticker or obj.get("tickerSymbol")
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk(value, key in ("about", "organization", "mainEntity"))

    for obj in p.ld:
        # Never borrow timestamps from nested related articles or publisher cards.
        if isinstance(obj, dict) and obj.get("@type") in (
            "Article",
            "NewsArticle",
            "BlogPosting",
            "PressRelease",
        ):
            published = published or _date(obj.get("datePublished"))
        walk(
            obj,
            isinstance(obj, dict)
            and obj.get("@type") in ("Organization", "Corporation", "PublicCompany"),
        )
    retrieved = retrieved_at or datetime.now(UTC)
    if retrieved.tzinfo is None:
        raise ValueError("retrieved_at must be timezone aware")
    doc = dict(
        url=url,
        title=" ".join(" ".join(p.title).split()),
        text=" ".join(" ".join(p.parts).split()),
        published_at=published,
        source_available_at=None,
        availability_basis="unknown_until_observed",
        content_revision_at=_date(p.meta.get("article:modified_time")),
        retrieved_at=retrieved.isoformat(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        raw_file=str(raw_file),
        source_kind=kind,
    )
    if isinstance(name, str) and name.strip():
        doc["company_name"] = name.strip()
    if isinstance(ticker, str) and ticker.strip():
        doc["ticker"] = ticker.strip()
    return doc


class PublicWebResearch:
    max_bytes = 2 * 1024 * 1024
    user_agent = "PublicResearchBot/1.0"

    def __init__(
        self,
        root,
        *,
        allow_network=False,
        max_requests=30,
        client=None,
        clock=None,
        primary_domains=None,
        discovery_feeds=None,
    ):
        self.allow_network = allow_network
        self.remaining = max(0, int(max_requests))
        self.client, self.clock = client, clock or (lambda: datetime.now(UTC))
        self.primary_domains = dict(primary_domains or {})
        self.attempts = []
        self.discovery_feeds = list(discovery_feeds or [])[:8]
        self.discovery_errors = []
        self._feed_cache = {}
        self._robots = {}
        self.run_dir = Path(root).resolve() / ("public-web-" + uuid4().hex)
        self.run_dir.mkdir(parents=True, exist_ok=False)

    def _validate(self, url):
        p = urlsplit(url)
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username
            or p.password
            or p.port not in (None, 443)
        ):
            raise ValueError("public HTTPS URL required")
        if any(
            re.search(r"(?i)api.?key|token|secret|password|authorization|credential|signature", key)
            for key, _ in parse_qsl(p.query)
        ):
            raise ValueError("secret query parameter denied")
        try:
            addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError("host resolution failed") from exc
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("non-public host denied")
        return addresses[0][4][0]

    def _request(self, url):
        for _ in range(5):
            address = self._validate(url)
            if not self.allow_network or self.remaining <= 0:
                raise ValueError("network disabled or request budget exhausted")
            self.remaining -= 1
            attempt = {"url": url, "request_started_at": self.clock().isoformat()}
            self.attempts.append(attempt)
            metadata_path = self.run_dir / f"{len(self.attempts):03d}-attempt.json"
            client = self.client or httpx.Client(timeout=10, follow_redirects=False, trust_env=True)
            try:
                # Preserve inherited proxy routing and destination policy. Proxied
                # connections rely on the trusted proxy to prevent DNS rebinding;
                # direct owned connections pin the verified public address.
                # Injected clients are trusted transports (normally MockTransport).
                proxied = any(
                    os.environ.get(key)
                    for key in (
                        "HTTPS_PROXY",
                        "https_proxy",
                        "HTTP_PROXY",
                        "http_proxy",
                        "ALL_PROXY",
                        "all_proxy",
                    )
                )
                host = urlsplit(url).hostname
                request_url = (
                    httpx.URL(url).copy_with(host=address)
                    if self.client is None and not proxied
                    else url
                )
                headers = {
                    "User-Agent": self.user_agent,
                    "Cookie": "",
                    "Authorization": "",
                    "Host": host,
                }
                with client.stream(
                    "GET",
                    request_url,
                    headers=headers,
                    extensions={"sni_hostname": host},
                    timeout=10,
                    follow_redirects=False,
                ) as response:
                    raw = bytearray()
                    started = time.monotonic()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if time.monotonic() - started > 20:
                            raise ValueError("response time limit exceeded")
                        if len(raw) > self.max_bytes:
                            raise ValueError("response exceeds size limit")
                    raw = bytes(raw)
                    attempt["retrieved_at"] = self.clock().isoformat()
                    sha = hashlib.sha256(raw).hexdigest()
                    stem = self.run_dir / f"{len(self.attempts):03d}-{sha}"
                    stem.with_suffix(".raw").write_bytes(raw)
                    attempt.update(
                        status=response.status_code,
                        raw_sha256=sha,
                        raw_file=str(stem.with_suffix(".raw")),
                    )
                    stem.with_suffix(".json").write_text(
                        json.dumps(attempt, sort_keys=True), encoding="utf-8"
                    )
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get("location", ""))
                        self._validate(url)
                        self._check_robots(url)
                        continue
                    response.raise_for_status()
                    return raw, attempt
            except Exception as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
                attempt["failed_at"] = self.clock().isoformat()
                raise
            finally:
                metadata_path.write_text(json.dumps(attempt, sort_keys=True), encoding="utf-8")
                if self.client is None:
                    client.close()
        raise ValueError("redirect limit exceeded")

    def _check_robots(self, url):
        p = urlsplit(url)
        origin = f"https://{p.netloc}"
        if origin not in self._robots:
            self._robots[origin] = None  # Fail closed, including redirect recursion.
            try:
                raw, _ = self._request(origin + "/robots.txt")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (404, 410):
                    raw = b""
                else:
                    raise ValueError("robots unavailable") from exc
            robot = RobotFileParser()
            robot.parse(raw.decode("utf-8", errors="replace").splitlines())
            self._robots[origin] = robot
        robot = self._robots[origin]
        if robot is None or not robot.can_fetch(self.user_agent, url):
            raise ValueError("robots denied or unavailable")

    def fetch(self, url):
        self._validate(url)
        self._check_robots(url)
        raw, meta = self._request(url)
        doc = parse_page(
            raw,
            meta["url"],
            retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
            raw_file=meta["raw_file"],
            primary_domains=self.primary_domains,
        )
        Path(meta["raw_file"]).with_suffix(".parsed.json").write_text(
            json.dumps(doc, sort_keys=True), encoding="utf-8"
        )
        return doc

    def _search_bing(self, query, limit=10):
        if not isinstance(query, str) or not query.strip():
            return []
        url = "https://www.bing.com/search?" + urlencode({"q": query, "format": "rss"})
        self._check_robots(url)
        raw, meta = self._request(url)
        if b"<!doctype" in raw.lower() or b"<!entity" in raw.lower():
            raise ValueError("unsafe search XML")
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as exc:
            raise ValueError("invalid search XML") from exc
        docs = []
        for item in root.findall(".//item")[: max(0, min(int(limit), 50))]:
            link = item.findtext("link") or ""
            try:
                self._validate(link)
            except ValueError:
                continue
            docs.append(
                dict(
                    url=link,
                    title=item.findtext("title") or "",
                    text="",
                    published_at=None,
                    retrieved_at=meta["retrieved_at"],
                    raw_sha256=meta["raw_sha256"],
                    raw_file=meta["raw_file"],
                    source_kind="unknown",
                )
            )
        Path(meta["raw_file"]).with_suffix(".parsed.json").write_text(
            json.dumps(docs, sort_keys=True), encoding="utf-8"
        )
        return docs

    def _feed_hits(self, url):
        if url in self._feed_cache:
            return self._feed_cache[url]
        self._check_robots(url)
        raw, meta = self._request(url)
        if b"<!doctype" in raw.lower() or b"<!entity" in raw.lower():
            raise ValueError("unsafe feed XML")
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as exc:
            raise ValueError("invalid feed XML") from exc
        hits = []
        entries = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in entries[:100]:
            link = item.findtext("link")
            if not link:
                atom = item.find("{http://www.w3.org/2005/Atom}link")
                link = atom.get("href") if atom is not None else None
            if not link:
                continue
            try:
                self._validate(link)
            except ValueError:
                continue
            title = (
                item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
            )
            hits.append(
                {
                    "url": link,
                    "title": title,
                    "text": "",
                    "published_at": None,
                    "retrieved_at": meta["retrieved_at"],
                    "raw_file": meta["raw_file"],
                    "raw_sha256": meta["raw_sha256"],
                    "source_kind": "unknown",
                    "discovery_feed": url,
                }
            )
        self._feed_cache[url] = hits
        return hits

    def search(self, query, limit=10):
        if not isinstance(query, str) or not query.strip():
            return []
        hits = []
        error = None
        try:
            hits = self._search_bing(query, limit)
        except (ValueError, httpx.HTTPError) as exc:
            error = exc
            self.discovery_errors.append({"source": "bing_rss", "error": str(exc)[:120]})
        tokens = set(re.findall(r"[\w-]{5,}", query.casefold())) - {
            "company",
            "investor",
            "relations",
            "acquisition",
            "investment",
        }
        site = re.search(r"site:([a-z0-9.-]+)", query, re.I)
        usable = False
        for feed in self.discovery_feeds:
            try:
                feed_hits = self._feed_hits(feed)
                usable = True
                for hit in feed_hits:
                    host = urlsplit(hit["url"]).hostname or ""
                    if site and host != site[1] and not host.endswith("." + site[1]):
                        continue
                    if tokens and not any(t in hit["title"].casefold() for t in tokens):
                        continue
                    hits.append(hit)
            except (ValueError, httpx.HTTPError) as exc:
                self.discovery_errors.append({"source": feed, "error": str(exc)[:120]})
        if error and not usable and not hits:
            raise error
        unique = {hit["url"]: hit for hit in hits}
        return list(unique.values())[: max(0, min(int(limit), 50))]
