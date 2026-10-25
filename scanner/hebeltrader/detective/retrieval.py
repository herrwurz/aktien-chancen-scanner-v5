"""Deterministic full-index Stage-A retrieval for unknown teasers."""

from pydantic import BaseModel, Field

from scanner.research import AssetIdentity
from scanner.research_index.identity import stable_asset_id
from scanner.research_index.models import CandidateQuery

from .schemas import AtomicClue

RRF_K = 60
CHANNEL_LIMIT = 50


class RetrievalExclusion(BaseModel):
    asset_id: str
    name: str
    reason: str


class RetrievalCandidate(BaseModel):
    asset_id: str
    identity: AssetIdentity
    rrf_score: int
    structured_score: int
    total_score: int
    channel_ranks: dict[str, int]
    uncertainties: list[str] = Field(default_factory=list)


class RetrievalReport(BaseModel):
    status: str
    candidates: list[RetrievalCandidate]
    exclusions: list[RetrievalExclusion] = Field(default_factory=list)
    full_universe_size: int = 0
    visible_universe_size: int = 0
    matched_before_limit: int = 0
    index_payload_sha256: str | None = None
    channel_counts: dict[str, int] = Field(default_factory=dict)
    coverage_warnings: list[str] = Field(default_factory=list)


def _values(clues, category):
    return sorted(
        {
            clue.value or clue.normalized
            for clue in clues
            if clue.category == category
            and clue.instrument_scope == "stock"
            and clue.polarity == "asserted"
        }
    )


def _queries(clues):
    channels = {}
    sectors = _values(clues, "sectors")
    countries = _values(clues, "countries")
    events = _values(clues, "events")
    facts = _values(clues, "fact_claims")
    if sectors:
        channels["sector"] = CandidateQuery(sectors=sectors)
    if countries:
        channels["country"] = CandidateQuery(countries=countries)
    if events or facts:
        channels["event"] = CandidateQuery(event_types=events, fact_claims=facts)
    text = sorted(
        {
            clue.value or clue.normalized
            for clue in clues
            if clue.instrument_scope == "stock"
            and clue.category
            in {"business", "products", "technologies", "market_position", "identifier"}
        }
    )
    if text:
        channels["text"] = CandidateQuery(text=" ".join(text))
    return channels


def _structured_score(identity, clues, present_channels):
    score = 0
    sectors = _values(clues, "sectors")
    countries = _values(clues, "countries")
    stock_ids = _values(clues, "identifier")
    if sectors:
        score += 20 if identity.sector in sectors else (-25 if identity.sector else 0)
    if countries:
        score += 8 if identity.country in countries else (-25 if identity.country else 0)
    if "event" in present_channels:
        score += 25
    identity_values = {identity.wkn, identity.isin, identity.ticker}
    if stock_ids and any(value in identity_values for value in stock_ids):
        score += 100
    if "text" in present_channels:
        score += 3
    return score


def retrieve_candidates(index, clues: list[AtomicClue], *, as_of, limit=50) -> RetrievalReport:
    if not 1 <= limit <= 50:
        raise ValueError("candidate limit must be between 1 and 50")
    queries = _queries(clues)
    if not queries:
        return RetrievalReport(status="insufficiently_constrained", candidates=[])
    records = {}
    full_size = visible_size = matched = 0
    payload_sha = None
    channel_counts = {}
    warnings = []
    for channel, query in sorted(queries.items()):
        batch = index.candidates(query, as_of=as_of, limit=CHANNEL_LIMIT)
        full_size = max(full_size, batch.full_universe_size)
        visible_size = max(visible_size, batch.visible_universe_size)
        matched += batch.matched_before_limit
        payload_sha = payload_sha or batch.index_payload_sha256
        warnings.extend(batch.coverage_warnings)
        channel_counts[channel] = len(batch.candidates)
        for rank, hit in enumerate(batch.candidates, 1):
            asset_id = stable_asset_id(hit.identity)
            row = records.setdefault(asset_id, {"identity": hit.identity, "ranks": {}})
            row["ranks"][channel] = rank
    candidates, exclusions = [], []
    for asset_id, row in records.items():
        identity = row["identity"]
        if identity.instrument_type in {"fund", "other"}:
            exclusions.append(
                RetrievalExclusion(
                    asset_id=asset_id,
                    name=identity.name,
                    reason="known_non_stock_instrument",
                )
            )
            continue
        ranks = row["ranks"]
        rrf_score = sum(round(1_000_000 / (RRF_K + rank)) for rank in ranks.values())
        structured = _structured_score(identity, clues, set(ranks))
        candidates.append(
            RetrievalCandidate(
                asset_id=asset_id,
                identity=identity,
                rrf_score=rrf_score,
                structured_score=structured,
                total_score=rrf_score + structured * 1000,
                channel_ranks=ranks,
                uncertainties=(
                    ["instrument_type_unverified"] if identity.instrument_type == "unknown" else []
                ),
            )
        )
    candidates.sort(key=lambda item: (-item.total_score, item.asset_id))
    return RetrievalReport(
        status="ok" if candidates else "unresolved",
        candidates=candidates[:limit],
        exclusions=sorted(exclusions, key=lambda item: item.asset_id),
        full_universe_size=full_size,
        visible_universe_size=visible_size,
        matched_before_limit=matched,
        index_payload_sha256=payload_sha,
        channel_counts=channel_counts,
        coverage_warnings=sorted(set(warnings)),
    )
