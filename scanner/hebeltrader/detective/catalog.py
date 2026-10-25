"""Synthetic point-in-time fixtures for deterministic detective tests."""

import hashlib
import json

from scanner.hebeltrader.detective.sources import OfflineFixtureSource

CATALOG_REVISION = "offline-fixture-v2-2026-10-23"


def _evidence(source_id, published_at, facts):
    payload = json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()
    return {
        "source_id": source_id,
        "url": f"fixture://detective/{source_id}",
        "title": "Synthetic point-in-time identification fixture",
        "published_at": published_at,
        "retrieved_at": published_at,
        "effective_at": published_at,
        "source_available_at": published_at,
        "source_kind": "fixture",
        "facts": facts,
        "content_sha256": hashlib.sha256(payload).hexdigest(),
    }


_CANDIDATES = [
    {
        "identity": {
            "asset_type": "stock",
            "name": "Johnson & Johnson",
            "ticker": "JNJ",
            "wkn": "853260",
            "isin": "US4781601046",
        },
        "aliases": ["johnson & johnson", "jnj"],
        "evidence": [
            _evidence(
                "jnj-2025-01",
                "2025-01-10T12:00:00Z",
                {
                    "sectors": ["healthcare", "pharma", "medical_technology"],
                    "countries": ["US"],
                    "events": ["dividend_growth"],
                    "metrics": {"dividend_years_min": 25},
                },
            )
        ],
    },
    {
        "identity": {
            "asset_type": "stock",
            "name": "Merck KGaA",
            "ticker": "MRK",
            "wkn": "659990",
            "isin": "DE0006599905",
        },
        "aliases": ["merck kgaa", "merck", "darmstadt"],
        "evidence": [
            _evidence(
                "merck-2025-01",
                "2025-01-12T12:00:00Z",
                {
                    "sectors": ["pharma", "laboratory"],
                    "countries": ["DE"],
                    "events": [],
                    "metrics": {},
                },
            )
        ],
    },
    {
        "identity": {
            "asset_type": "stock",
            "name": "adidas AG",
            "ticker": "ADS",
            "wkn": "A1EWWW",
            "isin": "DE000A1EWWW0",
        },
        "aliases": ["adidas"],
        "evidence": [
            _evidence(
                "adidas-2025-01",
                "2025-01-11T12:00:00Z",
                {
                    "sectors": ["sportswear"],
                    "countries": ["DE"],
                    "events": ["guidance_raise"],
                    "metrics": {},
                },
            )
        ],
    },
    {
        "identity": {
            "asset_type": "stock",
            "name": "E.ON SE",
            "ticker": "EOAN",
            "wkn": "ENAG99",
            "isin": "DE000ENAG999",
        },
        "aliases": ["e.on", "eon"],
        "evidence": [
            _evidence(
                "eon-2025-01",
                "2025-01-13T12:00:00Z",
                {
                    "sectors": ["energy", "power_grid"],
                    "countries": ["DE"],
                    "events": [],
                    "metrics": {},
                },
            )
        ],
    },
    {
        "identity": {
            "asset_type": "stock",
            "name": "Deere & Company",
            "ticker": "DE",
            "wkn": "850866",
            "isin": "US2441991054",
        },
        "aliases": ["deere", "john deere"],
        "evidence": [
            _evidence(
                "deere-2025-01",
                "2025-01-14T12:00:00Z",
                {
                    "sectors": ["agriculture_machinery"],
                    "countries": ["US"],
                    "events": [],
                    "metrics": {},
                },
            )
        ],
    },
    {
        "identity": {
            "asset_type": "stock",
            "name": "Bayer AG",
            "ticker": "BAYN",
            "wkn": "BAY001",
            "isin": "DE000BAY0017",
        },
        "aliases": ["bayer"],
        "evidence": [
            _evidence(
                "bayer-2025-01",
                "2025-01-15T12:00:00Z",
                {"sectors": ["pharma"], "countries": ["DE"], "events": [], "metrics": {}},
            )
        ],
    },
]

_PRODUCTS = [
    {
        "identity": {
            "asset_type": "derivative",
            "name": "HS5RMP candidate",
            "ticker": None,
            "wkn": "HS5RMP",
            "isin": None,
        },
        "underlying_wkn": "853260",
        "issuer": "HSBC",
        "maturity": "2026-01-16",
        "strike": "190 USD",
        "ratio": None,
        "evidence": _evidence(
            "hs5rmp-recommendation",
            "2025-08-05T06:00:00Z",
            {"document": "HEBELTRADER 130/2025 page 1", "official_termsheet": False},
        ),
    }
]


def default_candidate_source():
    return OfflineFixtureSource(_CANDIDATES)


def load_products():
    return list(_PRODUCTS)
