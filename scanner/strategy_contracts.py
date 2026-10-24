"""Research inputs for future strategies; deliberately no buy/sell decisions."""

from typing import Protocol

from scanner.research import AssetIdentity, CompanyEvent


class ShortTermTradingResearch(Protocol):
    def evaluate_inputs(self, asset: AssetIdentity, prices, events: list[CompanyEvent]): ...


class MediumTermInvestingResearch(Protocol):
    def evaluate_inputs(self, asset: AssetIdentity, fundamentals, events: list[CompanyEvent]): ...
