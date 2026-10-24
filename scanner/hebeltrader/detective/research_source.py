"""Adapter from shared normalized research records to detective candidates."""

from copy import deepcopy

from scanner.research import AssetIdentity, CompanyEvent, CompanyFact, EvidenceRecord


class ResearchCandidateSource:
    source_id = "normalized-research-snapshot"

    def __init__(self, assets, events, *, facts=(), coverage):
        self.assets = [AssetIdentity.model_validate(value) for value in assets]
        self.events = [CompanyEvent.model_validate(value) for value in events]
        self.facts = [CompanyFact.model_validate(value) for value in facts]
        self.coverage = deepcopy(coverage)
        self._events_by_key = self._index(self.events)
        self._facts_by_key = self._index(self.facts)

    @staticmethod
    def _index(records):
        result = {}
        for record in records:
            for key in (record.asset.cik, record.asset.isin):
                if key:
                    result.setdefault(key, []).append(record)
        return result

    @staticmethod
    def _records_for(index, identity):
        records = []
        seen = set()
        for key in (identity.cik, identity.isin):
            for record in index.get(key, []):
                marker = id(record)
                if marker not in seen:
                    records.append(record)
                    seen.add(marker)
        return records

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
        for event in self._records_for(self._events_by_key, identity):
            record = event.evidence.model_copy(deep=True)
            record.facts = dict(
                record.facts,
                sectors=[identity.sector] if identity.sector else [],
                countries=[identity.country] if identity.country else [],
                events=[event.category],
            )
            records.append(record.model_dump(mode="json"))
        for fact in self._records_for(self._facts_by_key, identity):
            record = EvidenceRecord(
                source_id=fact.fact_id,
                url=fact.source_url,
                title=f"{fact.metric}: {fact.claim}",
                published_at=fact.published_at,
                retrieved_at=fact.retrieved_at,
                effective_at=fact.published_at,
                source_available_at=fact.source_available_at,
                source_kind="regulatory",
                facts={
                    "sectors": [identity.sector] if identity.sector else [],
                    "countries": [identity.country] if identity.country else [],
                    "events": [],
                    "fact_claims": [
                        f"{fact.metric}_increase"
                        if fact.claim == "year_over_year_increase"
                        else f"{fact.metric}_decrease"
                        if fact.claim == "year_over_year_decrease"
                        else f"{fact.metric}_reported"
                    ],
                    "metric": fact.metric,
                    "value": str(fact.value),
                    "unit": fact.unit,
                    "comparison_value": (
                        str(fact.comparison_value) if fact.comparison_value is not None else None
                    ),
                    "source_location": fact.source_location,
                    "verification_status": fact.verification_status,
                },
                content_sha256=fact.content_sha256,
            )
            records.append(record.model_dump(mode="json"))
        return records
