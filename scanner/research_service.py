"""Provider-neutral research aggregation without strategy decisions."""

from collections import defaultdict
from typing import Protocol

from scanner.research import AssetIdentity, CompanyEvent, ProviderStatus


class UniverseProvider(Protocol):
    def load_universe(self) -> tuple[list[AssetIdentity], ProviderStatus]: ...


class EventProvider(Protocol):
    def load_events(self, identity: AssetIdentity) -> tuple[list[CompanyEvent], ProviderStatus]: ...


class PriceProvider(Protocol):
    def load_prices(self, identity: AssetIdentity, *, start, end): ...


class FundamentalProvider(Protocol):
    def load_fundamentals(self, identity: AssetIdentity, *, as_of): ...


def audit_identity_conflicts(assets):
    groups = defaultdict(list)
    for asset in assets:
        identity = AssetIdentity.model_validate(asset)
        for key in (identity.isin, identity.wkn):
            if key:
                groups[("security_id", key)].append(identity)
        if identity.ticker and identity.exchange:
            groups[("listing", identity.ticker, identity.exchange)].append(identity)
    conflicts = []
    duplicates = []
    for key, rows in groups.items():
        signatures = {(row.name, row.cik, row.isin, row.wkn, row.exchange) for row in rows}
        if len(rows) > 1 and len(signatures) == 1:
            duplicates.append({"key": key, "count": len(rows)})
        elif len(signatures) > 1:
            conflicts.append({"key": key, "assets": [row.model_dump(mode="json") for row in rows]})
    return {"duplicates": duplicates, "conflicts": conflicts, "merge_performed": False}


class ResearchService:
    def __init__(
        self,
        *,
        universe_provider,
        event_provider=None,
        price_provider=None,
        fundamental_provider=None,
    ):
        self.universe_provider = universe_provider
        self.event_provider = event_provider
        self.price_provider = price_provider
        self.fundamental_provider = fundamental_provider

    def universe(self):
        assets, status = self.universe_provider.load_universe()
        return {
            "assets": [asset.model_dump(mode="json") for asset in assets],
            "provider_status": status.model_dump(mode="json"),
            "identity_audit": audit_identity_conflicts(assets),
            "strategy_decision": None,
        }

    def events(self, identity):
        if self.event_provider is None:
            return {
                "events": [],
                "provider_status": {"status": "unavailable"},
                "strategy_decision": None,
            }
        events, status = self.event_provider.load_events(AssetIdentity.model_validate(identity))
        return {
            "events": [event.model_dump(mode="json") for event in events],
            "provider_status": status.model_dump(mode="json"),
            "strategy_consumers": [
                "HEBELTRADER_DETECTIVE",
                "short_term_trading",
                "medium_term_investing",
            ],
            "strategy_decision": None,
        }

    def prices(self, identity, *, start, end):
        if self.price_provider is None:
            return {"prices": [], "provider_status": {"status": "unavailable"}}
        return self.price_provider.load_prices(
            AssetIdentity.model_validate(identity), start=start, end=end
        )

    def fundamentals(self, identity, *, as_of):
        if self.fundamental_provider is None:
            return {"fundamentals": [], "provider_status": {"status": "unavailable"}}
        return self.fundamental_provider.load_fundamentals(
            AssetIdentity.model_validate(identity), as_of=as_of
        )
