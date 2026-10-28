from scanner.hebeltrader.detective.product_research import research_calls


class Web:
    def __init__(self):
        self.queries = []
        self.urls = []

    def search(self, query, limit):
        self.queries.append(query)
        return [
            {"url": u}
            for u in [
                "https://issuer.example.evil/p",
                "https://issuer.example/p",
                "https://evil.example/p",
            ]
        ]

    def fetch(self, url):
        self.urls.append(url)
        return {
            "url": url,
            "text": (
                "WKN: AB12CD\nISIN: DE000AB12CD3\nBasispreis: 250,00 USD\n"
                "Laufzeit: 20.12.2027\nBezugsverhältnis: 0,1\nRendite 1191 %"
            ),
        }


def identified():
    return {
        "identification": {"status": "identified"},
        "candidates": [{"asset_id": "company:example", "identity": {"name": "Example AG"}}],
    }


def test_gates_no_network():
    web = Web()
    assert research_calls(identified(), web, {}, "")["status"] == "not_identified"
    assert (
        research_calls(
            {"identification": {"status": "not_identified"}}, web, {"Issuer": "issuer.example"}, ""
        )["status"]
        == "not_identified"
    )
    assert not web.queries


def test_official_only_literal_terms_no_advertised_call_claim():
    web = Web()
    result = research_calls(identified(), web, {"Issuer": "issuer.example"}, "1191 % WKN AB12CD")
    assert web.urls == ["https://issuer.example/p"]
    assert "Example AG" in web.queries[0]
    product = result["candidates"][0]
    assert product["wkn"] == "AB12CD"
    assert product["strike"] == "250,00 USD"
    assert product["ratio"] == "0,1"
    assert product["source"]["sha256"]
    assert product["verification_status"] == "manual_review_required"
    assert result["actual_hebeltrader_call_identified"] is False


def test_missing_terms_null_and_redirect_rejected():
    web = Web()
    web.fetch = lambda url: {"url": "https://evil.example/final", "text": "WKN: AB12CD"}
    assert research_calls(identified(), web, {"Issuer": "issuer.example"}, "")["candidates"] == []
    web.fetch = lambda url: {"url": url, "text": "unlabelled AB12CD 250 2027"}
    product = research_calls(identified(), web, {"Issuer": "issuer.example"}, "")["candidates"][0]
    assert all(product[key] is None for key in ("wkn", "isin", "strike", "maturity", "ratio"))
