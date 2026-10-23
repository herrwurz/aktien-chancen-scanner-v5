from copy import deepcopy

CATALOG_REVISION = "mvp-2026-10-23"

# Small bootstrap catalog. Entries are identification candidates, not recommendations.
_CANDIDATES = [
    {
        "name": "Johnson & Johnson",
        "ticker": "JNJ",
        "wkn": "853260",
        "isin": "US4781601046",
        "aliases": ["johnson & johnson", "jnj"],
        "keywords": ["pharma", "gesundheit", "healthcare", "dividende", "us-konzern"],
        "sources": [{"url": "https://www.jnj.com/", "as_of": "2026-10-23", "kind": "issuer"}],
        "calls": [
            {
                "wkn": "HS5RMP",
                "isin": None,
                "issuer": "HSBC",
                "maturity": "2026-01-16",
                "strike": "190 USD",
                "ratio": None,
                "status": "recommendation_observed_terms_unverified",
                "source": "HEBELTRADER 130/2025 page 1; official termsheet still required",
            }
        ],
    },
    {
        "name": "adidas AG",
        "ticker": "ADS",
        "wkn": "A1EWWW",
        "isin": "DE000A1EWWW0",
        "aliases": ["adidas"],
        "keywords": ["sportartikel", "sneaker", "dax", "herzogenaurach"],
        "sources": [
            {"url": "https://www.adidas-group.com/", "as_of": "2026-10-23", "kind": "issuer"}
        ],
        "calls": [],
    },
    {
        "name": "Merck KGaA",
        "ticker": "MRK",
        "wkn": "659990",
        "isin": "DE0006599905",
        "aliases": ["merck kgaa", "merck", "darmstadt"],
        "keywords": ["pharma", "wissenschaft", "dax", "labor"],
        "sources": [
            {"url": "https://www.merckgroup.com/", "as_of": "2026-10-23", "kind": "issuer"}
        ],
        "calls": [],
    },
    {
        "name": "E.ON SE",
        "ticker": "EOAN",
        "wkn": "ENAG99",
        "isin": "DE000ENAG999",
        "aliases": ["e.on", "eon"],
        "keywords": ["energie", "stromnetz", "dax", "netzbetreiber"],
        "sources": [{"url": "https://www.eon.com/", "as_of": "2026-10-23", "kind": "issuer"}],
        "calls": [],
    },
    {
        "name": "Deere & Company",
        "ticker": "DE",
        "wkn": "850866",
        "isin": "US2441991054",
        "aliases": ["deere", "john deere"],
        "keywords": ["landmaschinen", "traktor", "agrar", "usa"],
        "sources": [{"url": "https://www.deere.com/", "as_of": "2026-10-23", "kind": "issuer"}],
        "calls": [],
    },
]


def load_catalog():
    return deepcopy(_CANDIDATES)
