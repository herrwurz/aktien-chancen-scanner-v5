"""Research inputs for future strategies; deliberately no buy/sell decisions."""

from typing import Protocol

from scanner.research import AssetIdentity, CompanyEvent


class ShortTermTradingResearch(Protocol):
    def evaluate_inputs(self, asset: AssetIdentity, prices, events: list[CompanyEvent]): ...


class MediumTermInvestingResearch(Protocol):
    def evaluate_inputs(self, asset: AssetIdentity, fundamentals, events: list[CompanyEvent]): ...


REQUIRED_FIELDS = {
    "short_term_trading": [
        "price",
        "volume",
        "company_event",
        "timestamp",
        "liquidity",
    ],
    "medium_term_investing": [
        "fundamentals",
        "growth",
        "valuation",
        "trend",
        "catalyst",
    ],
}


def assess_strategy_inputs(strategy, availability):
    if strategy not in REQUIRED_FIELDS:
        raise ValueError("unsupported strategy")
    required = REQUIRED_FIELDS[strategy]
    fields = {name: availability.get(name, "missing") for name in required}
    missing = [name for name, status in fields.items() if status != "available"]
    return {
        "strategy": strategy,
        "required_fields": required,
        "field_availability": fields,
        "missing_fields": missing,
        "status": "ready" if not missing else "incomplete",
        "strategy_decision": None,
    }
