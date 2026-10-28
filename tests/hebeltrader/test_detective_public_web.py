from datetime import UTC, datetime

import httpx
import pytest

from scanner.hebeltrader.detective.public_web import PublicWebResearch, parse_page

NOW = datetime(2026, 10, 28, tzinfo=UTC)


def test_page_metadata_identity_and_real_dates():
    raw = b"""<title>Growth</title>
<meta property="article:published_time" content="2025-01-02T12:30:00Z">
<script type="application/ld+json">
{"@type":"NewsArticle",
"about":{"@type":"Organization","name":"Example AG","tickerSymbol":"EX"}}
</script><p>Revenue rose</p>"""
    doc = parse_page(raw, "https://example.com/news", retrieved_at=NOW)
    assert doc["company_name"] == "Example AG"
    assert doc["ticker"] == "EX"
    assert doc["published_at"] == "2025-01-02T12:30:00+00:00"
    assert doc["source_kind"] == "news"
    assert "Revenue rose" in doc["text"]


def test_no_identity_or_invented_date():
    doc = parse_page(
        b"<title>Acme investor relations</title>", "https://random.com/investors", retrieved_at=NOW
    )
    assert "company_name" not in doc
    assert doc["published_at"] is None
    assert doc["source_kind"] != "issuer"


def test_network_disabled_and_private_urls(tmp_path):
    r = PublicWebResearch(tmp_path)
    with pytest.raises(ValueError):
        r.fetch("https://example.com")
    assert r.remaining == 30
    with pytest.raises(ValueError):
        r.fetch("https://127.0.0.1/")


def test_robots_budget_archives_and_errors(tmp_path, monkeypatch):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="<title>Public</title><p>Evidence</p>")

    r = PublicWebResearch(
        tmp_path,
        allow_network=True,
        max_requests=3,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
    )
    monkeypatch.setattr(r, "_validate", lambda url: None)
    with pytest.raises(ValueError, match="robots"):
        r.fetch("https://example.com/private")
    doc = r.fetch("https://example.com/public")
    assert doc["raw_file"]
    assert r.remaining == 1
    assert len(r.attempts) == 2
    assert len(list(r.run_dir.glob("*.raw"))) == 2


def test_search_is_global_hints(tmp_path, monkeypatch):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            text=(
                "<rss><channel><item><title>Discovery</title>"
                "<link>https://company.example/news</link>"
                "<pubDate>Wed, 01 Jan 2020 00:00:00 GMT</pubDate></item></channel></rss>"
            ),
        )

    r = PublicWebResearch(
        tmp_path, allow_network=True, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    monkeypatch.setattr(r, "_validate", lambda url: None)
    docs = r.search("unusual teaser phrase")
    assert docs[0]["text"] == ""
    assert docs[0]["published_at"] is None
    assert docs[0]["url"] == "https://company.example/news"


def test_http_error_is_explicit_and_archived(tmp_path, monkeypatch):
    def handler(req):
        return httpx.Response(404 if req.url.path == "/robots.txt" else 403)

    r = PublicWebResearch(
        tmp_path, allow_network=True, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    monkeypatch.setattr(r, "_validate", lambda url: None)
    with pytest.raises(httpx.HTTPStatusError):
        r.fetch("https://example.com/paywall")
    assert r.attempts[-1]["status"] == 403
    assert r.attempts[-1]["error"]
    assert len(list(r.run_dir.glob("*.raw"))) == 2


def test_approved_domain_only_and_aware_date():
    doc = parse_page(
        b'<meta property="article:published_time" content="2025-01-02">',
        "https://issuer.example/news",
        primary_domains={"issuer.example": "Approved AG"},
    )
    assert doc["source_kind"] == "issuer"
    assert doc["company_name"] == "Approved AG"
    assert doc["published_at"] is None
    assert parse_page(b"", "https://www.sec.gov/Archives")["source_kind"] == "regulatory"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pw@example.com",
        "https://example.com?api%5Fkey=secret",
        "https://127.0.0.1",
        "https://[::1]",
    ],
)
def test_unsafe_urls_rejected(tmp_path, url):
    r = PublicWebResearch(tmp_path)
    with pytest.raises(ValueError):
        r._validate(url)


@pytest.mark.parametrize(
    "raw",
    [
        b'<script type="application/ld+json">{'
        b'"isAccessibleForFree": false, "articleBody":"Hidden paid content"}</script>',
        b'<meta name="requires_login" content="true"><p>Private</p>',
        b'<meta name="paywall" content="premium">',
    ],
)
def test_paid_or_login_metadata_denies_extraction(raw):
    with pytest.raises(ValueError, match="paywall|login"):
        parse_page(raw, "https://example.com/article")


def test_archives_are_absolute(tmp_path):
    r = PublicWebResearch(tmp_path)
    assert r.run_dir.is_absolute()


def test_receipt_time_is_after_complete_response_and_failure_is_archived(tmp_path, monkeypatch):
    times = iter(datetime(2026, 10, 28, 12, 0, second, tzinfo=UTC) for second in range(10))
    r = PublicWebResearch(
        tmp_path,
        allow_network=True,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text="ok"))
        ),
        clock=lambda: next(times),
    )
    monkeypatch.setattr(r, "_validate", lambda url: None)
    _, meta = r._request("https://example.com/page")
    assert meta["retrieved_at"] > meta["request_started_at"]


def test_malformed_search_response_is_explicit_data_gap(tmp_path, monkeypatch):
    r = PublicWebResearch(tmp_path, allow_network=True)
    monkeypatch.setattr(r, "_check_robots", lambda url: None)
    monkeypatch.setattr(r, "_request", lambda url: (b"not XML", {}))
    with pytest.raises(ValueError, match="invalid search XML"):
        r.search("sample")


def test_related_article_date_is_not_the_original_publication():
    raw = (
        b'<script type="application/ld+json">{"@type":"NewsArticle", '
        b'"relatedLink":{"@type":"NewsArticle", '
        b'"datePublished":"2025-01-02T12:30:00Z"}}</script>'
    )
    assert parse_page(raw, "https://example.com/news")["published_at"] is None
