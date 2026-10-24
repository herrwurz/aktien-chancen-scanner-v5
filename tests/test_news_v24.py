from datetime import UTC, datetime

import httpx
import pytest

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def item(**updates):
    from scanner.news import NewsItem

    values = dict(
        source_id="issuer:1",
        source_type="PRIMARY",
        url="https://issuer.example/news/1",
        title="Example raises full-year guidance",
        published_at=NOW,
        first_seen_at=NOW,
        retrieved_at=NOW,
        source_available_at=NOW,
        company_identifiers={"isin": ["DE000TEST001"]},
        event_type="guidance_raise",
        event_confidence="source_claim",
        evidence_status="source_document",
        license_status="permitted_metadata",
        content_hash="a" * 64,
        origin_id="issuer:1",
    )
    values.update(updates)
    return NewsItem(**values)


def test_news_contract_rejects_community_as_verified_company_fact():
    from scanner.news import NewsItem

    values = item().model_dump()
    values.update(source_type="COMMUNITY", evidence_status="verified_company_fact")
    with pytest.raises(ValueError, match="community evidence"):
        NewsItem(**values)


def test_cluster_syndicated_copies_count_one_independent_origin():
    from scanner.news_cluster import cluster_news

    copy = item(
        source_id="portal:9",
        source_type="SECONDARY",
        url="https://portal.example/copy",
        origin_id="issuer:1",
        content_hash="b" * 64,
    )
    clusters = cluster_news([item(), copy])
    assert len(clusters) == 1
    assert clusters[0].publication_urls == [
        "https://issuer.example/news/1",
        "https://portal.example/copy",
    ]
    assert clusters[0].independent_origin_count == 1
    assert clusters[0].strongest_source_type == "PRIMARY"


def test_distinct_origins_with_similar_title_remain_one_event_but_two_origins():
    from scanner.news_cluster import cluster_news

    second = item(
        source_id="news:2",
        source_type="SECONDARY",
        url="https://news.example/2",
        origin_id="news:2",
        content_hash="b" * 64,
    )
    cluster = cluster_news([item(), second])[0]
    assert cluster.independent_origin_count == 2


def test_gdelt_normalizes_metadata_without_claiming_article_rights(tmp_path):
    from scanner.news_providers.gdelt import GdeltNewsSource

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "url": "https://publisher.example/story",
                        "title": "Example wins major contract",
                        "seendate": "20261024T101500Z",
                        "domain": "publisher.example",
                        "language": "English",
                        "sourcecountry": "United States",
                    }
                ]
            },
        )

    source = GdeltNewsSource(
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
    )
    batch = source.fetch(
        "Example contract",
        start=datetime(2026, 10, 24, tzinfo=UTC),
        end=NOW,
        limit=10,
        company_identifiers={"cik": ["42"]},
    )
    assert len(calls) == 1
    assert batch.status == "ok"
    record = batch.items[0]
    assert record.source_type == "SECONDARY"
    assert record.license_status == "metadata_only"
    assert record.company_identifiers == {"cik": ["42"]}
    assert record.source_available_at == NOW
    assert record.published_at == datetime(2026, 10, 24, 10, 15, tzinfo=UTC)
    assert "content" not in record.model_dump()


def test_gdelt_cache_is_offline_and_sha_verified(tmp_path):
    from scanner.news_providers.gdelt import GdeltNewsSource

    payload = {"articles": []}
    online = GdeltNewsSource(
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
        clock=lambda: NOW,
    )
    kwargs = dict(start=datetime(2026, 10, 24, tzinfo=UTC), end=NOW, limit=10)
    online.fetch("Example", **kwargs)
    offline = GdeltNewsSource(tmp_path, allow_network=False, max_requests=0, clock=lambda: NOW)
    assert offline.fetch("Example", **kwargs).cache_hit is True
    raw = next((tmp_path / "raw").glob("*.json"))
    raw.write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        offline.fetch("Example", **kwargs)


def test_gdelt_requires_explicit_network_and_bounded_limit(tmp_path):
    from scanner.news_providers.gdelt import GdeltNewsSource

    source = GdeltNewsSource(tmp_path, allow_network=False, max_requests=0, clock=lambda: NOW)
    with pytest.raises(ValueError, match="explicit network"):
        source.fetch("uncached", start=NOW, end=NOW, limit=10)
    with pytest.raises(ValueError, match="limit"):
        source.fetch("uncached", start=NOW, end=NOW, limit=251)


def test_allowlisted_rss_maps_only_configured_identifier(tmp_path):
    from scanner.news_providers.issuer_feed import IssuerFeedConfig, IssuerFeedNewsSource

    xml = b"""<?xml version='1.0'?><rss version='2.0'><channel><title>Example IR</title>
    <item><guid>release-1</guid><title>Example reports results</title>
    <link>https://issuer.example/release-1</link><pubDate>Sat, 24 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    config = IssuerFeedConfig(
        url="https://issuer.example/feed.xml",
        issuer_name="Example AG",
        company_identifiers={"isin": ["DE000TEST001"]},
        license_status="permitted_metadata",
        license_reference="https://issuer.example/feed-terms",
    )
    source = IssuerFeedNewsSource(
        [config],
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=xml))
        ),
        clock=lambda: NOW,
    )
    batch = source.fetch("Example AG", start=datetime(2026, 10, 24, tzinfo=UTC), end=NOW, limit=10)
    assert batch.items[0].source_type == "PRIMARY"
    assert batch.items[0].company_identifiers == {"isin": ["DE000TEST001"]}
    assert batch.items[0].evidence_status == "issuer_publication"


def test_issuer_feed_refuses_unknown_license_and_unsafe_xml(tmp_path):
    from scanner.news_providers.issuer_feed import IssuerFeedConfig, IssuerFeedNewsSource

    with pytest.raises(ValueError, match="license"):
        IssuerFeedConfig(
            url="https://issuer.example/feed.xml",
            issuer_name="Example",
            company_identifiers={"isin": ["DE000TEST001"]},
            license_status="unknown",
            license_reference="",
        )
    config = IssuerFeedConfig(
        url="https://issuer.example/feed.xml",
        issuer_name="Example",
        company_identifiers={"isin": ["DE000TEST001"]},
        license_status="permitted_metadata",
        license_reference="https://issuer.example/terms",
    )
    xml = b"<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><rss/>"
    source = IssuerFeedNewsSource(
        [config],
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=xml))
        ),
        clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="unsafe XML"):
        source.fetch("Example", start=NOW, end=NOW, limit=10)


def test_issuer_feed_replays_sha_verified_cache_without_network(tmp_path):
    from scanner.news_providers.issuer_feed import IssuerFeedConfig, IssuerFeedNewsSource

    xml = b"""<rss><channel><item><guid>1</guid><title>Example update</title>
    <link>https://issuer.example/1</link><pubDate>Sat, 24 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    config = IssuerFeedConfig(
        url="https://issuer.example/feed.xml",
        issuer_name="Example",
        company_identifiers={"cik": ["42"]},
        license_status="permitted_metadata",
        license_reference="https://issuer.example/terms",
    )
    online = IssuerFeedNewsSource(
        [config],
        tmp_path,
        allow_network=True,
        max_requests=1,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=xml))
        ),
        clock=lambda: NOW,
    )
    online.fetch("Example", start=NOW.replace(hour=0), end=NOW, limit=10)
    offline = IssuerFeedNewsSource(
        [config], tmp_path, allow_network=False, max_requests=0, clock=lambda: NOW
    )
    replay = offline.fetch("Example", start=NOW.replace(hour=0), end=NOW, limit=10)
    assert replay.cache_hit is True
    assert replay.request_count == 0


def test_news_identity_linker_requires_unique_bounded_name_or_ticker():
    from scanner.news_identity import link_news_to_assets
    from scanner.research import AssetIdentity

    acme = AssetIdentity(asset_type="stock", name="Acme Corp", ticker="ACME", cik="1")
    acme_labs = AssetIdentity(asset_type="stock", name="Acme Labs", ticker="LAB", cik="2")
    linked = link_news_to_assets(
        [item(title="Acme Corp raises guidance", company_identifiers={})], [acme, acme_labs]
    )
    assert linked[0].company_identifiers == {"cik": ["1"]}
    assert linked[0].evidence_status == "identity_candidate_exact_alias"


def test_news_identity_linker_does_not_choose_between_duplicate_names():
    from scanner.news_identity import link_news_to_assets
    from scanner.research import AssetIdentity

    assets = [
        AssetIdentity(asset_type="stock", name="Example Holdings", ticker="EXA", cik="1"),
        AssetIdentity(asset_type="stock", name="Example Holdings", ticker="EXB", cik="2"),
    ]
    linked = link_news_to_assets(
        [item(title="Example Holdings reports", company_identifiers={})], assets
    )
    assert linked[0].company_identifiers == {}
    assert linked[0].evidence_status == "identity_unresolved"
