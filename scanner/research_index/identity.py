"""Canonical identifiers shared by research and market-data artifacts."""

import re

from scanner.research import AssetIdentity


def canonical_cik(value: str) -> str:
    text = str(value)
    if not re.fullmatch(r"[0-9]{1,10}", text) or int(text) <= 0:
        raise ValueError("invalid SEC CIK")
    return text.zfill(10)


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
