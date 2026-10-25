"""Canonical identifiers shared by research and market-data artifacts."""

import re

from scanner.research import AssetIdentity

EXCHANGE_ALIASES = {
    "nasdaq": "NASDAQ",
    "nasdaq stock market": "NASDAQ",
    "nyse": "NYSE",
    "new york stock exchange": "NYSE",
    "nyse american": "NYSE_AMERICAN",
}


def canonical_cik(value: str) -> str:
    text = str(value)
    if not re.fullmatch(r"[0-9]{1,10}", text) or int(text) <= 0:
        raise ValueError("invalid SEC CIK")
    return text.zfill(10)


def canonical_exchange(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().casefold().split())
    return EXCHANGE_ALIASES.get(normalized, normalized.upper())


def canonicalize_identity(value) -> AssetIdentity:
    identity = AssetIdentity.model_validate(value)
    if identity.cik is None:
        return identity
    return identity.model_copy(update={"cik": canonical_cik(identity.cik)})


def stable_asset_id(value) -> str:
    identity = canonicalize_identity(value)
    for kind in ("cik", "isin", "wkn", "lei"):
        identifier = getattr(identity, kind)
        if identifier:
            return f"{kind}:{identifier}"
    raise ValueError("stable identifier required")
