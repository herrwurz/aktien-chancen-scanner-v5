"""Conservative news-to-equity candidate linking using unique bounded aliases."""

import re

from scanner.news import NewsItem
from scanner.research import AssetIdentity


def _present(text, alias):
    return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.IGNORECASE) is not None


def link_news_to_assets(items, assets):
    identities = [AssetIdentity.model_validate(row) for row in assets]
    result = []
    for value in items:
        item = NewsItem.model_validate(value)
        matches = []
        for identity in identities:
            aliases = [identity.name]
            if identity.ticker and len(identity.ticker) >= 3:
                aliases.append(identity.ticker)
            if any(_present(item.title, alias) for alias in aliases):
                matches.append(identity)
        if len(matches) != 1:
            result.append(
                item.model_copy(
                    update={
                        "company_identifiers": {},
                        "evidence_status": "identity_unresolved",
                    }
                )
            )
            continue
        identity = matches[0]
        identifiers = {
            kind: [value]
            for kind in ("cik", "isin", "wkn", "lei")
            if (value := getattr(identity, kind))
        }
        result.append(
            item.model_copy(
                update={
                    "company_identifiers": identifiers,
                    "evidence_status": "identity_candidate_exact_alias",
                }
            )
        )
    return result
