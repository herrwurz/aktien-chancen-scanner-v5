"""Public catalog extraction and dedup; synthetic markup contains no solved cases."""

from datetime import UTC, datetime

import pytest
from test_teaser_monitor import Engine

from scanner.hebeltrader.detective.monitor import TeaserMonitor
from scanner.hebeltrader.detective.publisher_catalog import catalog_links, product_teaser

URL = "https://www.boersenmedien.de/produkt/hebeltrader/hebeltrader-20126-6001.html"
CAT = "https://www.boersenmedien.de/hebeltrader"
HTML = """<header><h1>HEBELTRADER 201/26</h1>
<div class="product-info"><time datetime="2026-10-29">29.10.2026</time>
</div></header>
<div class="single-purchase-buy"><form>Buy now<input type="hidden" value="secret"></form></div>
<div class="single-purchase-detail">
<div class="product-info"><span>Autor:</span><strong>Rudolf Wittmer</strong>
</div>
<div class="single-purchase-description"><p>Liquidity warning.</p>
<p><h2>Neue Industrie-Chance</h2></p>
<p>Ein unbekannter Konzern liefert KI-Kühlung. Bis zu 421 Prozent mit einem Call.</p>
<p>Aktuelle Analyse.</p></div></div>
<aside><h2>Andere Ausgabe</h2><time datetime="2025-01-01">Alt</time>
<p>Andere Aktie ist SECRET CORP.</p><a href="/download/paid.pdf">PDF</a></aside>"""
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def test_catalog_only_discovers_public_product_pages_and_canonicalizes():
    raw = (
        f'<a href="{URL}?utm_source=test">Issue</a><a href="{URL}">Duplicate</a>'
        '<a href="https://evil.example/produkt/hebeltrader/hebeltrader-20226-9999.html">Bad</a>'
        '<a href="/download/paid.pdf">PDF</a>'
    )
    assert catalog_links(raw, CAT, limit=3) == [URL]


def test_product_extracts_only_teaser_and_its_own_day_not_sidebar():
    doc = product_teaser(HTML, URL)
    assert doc["issue"] == "201/26"
    assert doc["author"] == "Rudolf Wittmer"
    assert doc["publication_date"] == "2026-10-29"
    assert doc["published_at"] is None
    assert doc["title"] == "Neue Industrie-Chance"
    assert "KI-Kühlung" in doc["text"]
    assert all(x not in doc["text"] for x in ["SECRET CORP", "Liquidity warning", "Buy now"])


def test_unknown_layout_and_non_product_urls_fail_closed():
    with pytest.raises(ValueError):
        product_teaser("<p>Plain promotion</p>", URL)
    with pytest.raises(ValueError):
        product_teaser(HTML, "https://evil.example/produkt/hebeltrader/hebeltrader-20126-6001.html")


def test_catalog_monitor_reuses_existing_dedup_and_preserves_source_metadata(tmp_path):
    catalog = tmp_path / "catalog.html"
    catalog.write_text(f'<a href="{URL}">HEBELTRADER 201/26</a>')
    product = tmp_path / "product.html"
    product.write_text(HTML)

    class Web:
        def search(self, query, limit=20):
            return []

        def fetch(self, url):
            assert url in (CAT, URL), "Unexpected paid or third-party fetch"
            return {
                "url": url,
                "raw_file": str(catalog if url == CAT else product),
                "raw_sha256": "raw",
                "retrieved_at": NOW.isoformat(),
            }

    class RecordedEngine(Engine):
        def analyze(self, request):
            self.request = request
            return super().analyze(request)

    engine = RecordedEngine()
    monitor = TeaserMonitor(
        tmp_path / "monitor", web=Web(), engine=engine, clock=lambda: NOW, catalog_urls=[CAT]
    )
    first = monitor.scan_once()
    second = monitor.scan_once()
    assert first["new_teasers"] == 1 and second["new_teasers"] == 0
    assert engine.calls == 1 and len(monitor.notifications()) == 1
    assert engine.request.issue == "201/26"
    assert engine.request.publication_date.isoformat() == "2026-10-29"
    assert engine.request.publication_at is None
    assert engine.request.author == "Rudolf Wittmer"


def test_hidden_markup_is_not_public_teaser_text():
    page = HTML.replace(
        "<p>Aktuelle Analyse.</p>",
        "<p hidden>Hidden solution: SECRET CORP</p>"
        '<span style="display:none">Paid PDF contents</span>'
        "<p>Aktuelle Analyse.</p>",
    )
    document = product_teaser(page, URL)
    assert "SECRET CORP" not in document["text"]
    assert "Paid PDF" not in document["text"]


def test_product_heading_must_match_url_issue():
    with pytest.raises(ValueError, match="disagree"):
        product_teaser(HTML.replace("HEBELTRADER 201/26", "HEBELTRADER 200/26"), URL)
