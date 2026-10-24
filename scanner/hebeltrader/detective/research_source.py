"""Adapter from shared normalized research records to detective candidates."""

from copy import deepcopy

from scanner.research import AssetIdentity, CompanyEvent


class ResearchCandidateSource:
    source_id = "normalized-research-snapshot"

    def __init__(self, assets, events, *, coverage):
        self.assets = [AssetIdentity.model_validate(value) for value in assets]
        self.events = [CompanyEvent.model_validate(value) for value in events]
        self.coverage = deepcopy(coverage)

    def load_candidates(self):
        return [
            {
                "identity": asset.model_dump(mode="json"),
                "aliases": [asset.name, asset.ticker] if asset.ticker else [asset.name],
            }
            for asset in self.assets
        ]

    def evidence_for(self, identity):
        records = []
        for event in self.events:
            same_asset = (identity.cik and event.asset.cik == identity.cik) or (
                identity.isin and event.asset.isin == identity.isin
            )
            if not same_asset:
                continue
            record = event.evidence.model_copy(deep=True)
            record.facts = dict(
                record.facts,
                sectors=[identity.sector] if identity.sector else [],
                countries=[identity.country] if identity.country else [],
                events=[event.category],
            )
            records.append(record.model_dump(mode="json"))
        return records
