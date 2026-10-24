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


class IndexedResearchService:
    """Shared read-only index facade; it never creates a strategy decision."""

    def __init__(self, index, *, price_archive=None):
        self.index = index
        self.price_archive = price_archive

    def universe(self, *, as_of):
        return {**self.index.coverage(as_of), "strategy_decision": None}

    def candidates(self, query, *, as_of, limit=50):
        result = self.index.candidates(query, as_of=as_of, limit=limit)
        return {
            **result.model_dump(mode="json"),
            "strategy_consumers": [
                "HEBELTRADER_DETECTIVE",
                "short_term_trading",
                "medium_term_investing",
            ],
            "strategy_decision": None,
        }

    def events(self, identity, *, as_of):
        return self.index.evidence(identity, as_of=as_of, kinds={"event", "news"})

    def fundamentals(self, identity, *, as_of):
        return self.index.evidence(identity, as_of=as_of, kinds={"fact"})

    def prices(
        self,
        identity,
        *,
        as_of,
        start=None,
        end=None,
        availability_mode="strict",
    ):
        if self.price_archive is None:
            return {
                "status": "unavailable",
                "prices": [],
                "as_of": as_of.isoformat(),
                "reason": "market_data_archive_not_configured",
                "strategy_decision": None,
            }
        resolved = self.index.resolve_identity(identity, as_of=as_of)
        if resolved["status"] != "ok":
            return {
                **resolved,
                "prices": [],
                "as_of": as_of.isoformat(),
                "strategy_decision": None,
            }
        day = as_of.date().isoformat()
        result = self.price_archive.prices(
            resolved["asset_id"],
            start=start or "0001-01-01",
            end=end or day,
            as_of=as_of,
            availability_mode=availability_mode,
        )
        return {
            **result,
            "asset_id": resolved["asset_id"],
            "strategy_decision": None,
        }

    def coverage(self, *, as_of):
        return self.index.coverage(as_of)

    def strategy_availability(self, identity, *, as_of):
        identity = AssetIdentity.model_validate(identity)
        return {
            "asset": identity.model_dump(mode="json"),
            "as_of": as_of.isoformat(),
            "short_term_trading": {
                "required": ["price", "volume", "event", "liquidity"],
                "decision_status": "unavailable",
            },
            "medium_term_investing": {
                "required": ["fundamentals", "growth", "valuation", "trend", "catalysts"],
                "decision_status": "unavailable",
            },
            "strategy_decision": None,
        }
