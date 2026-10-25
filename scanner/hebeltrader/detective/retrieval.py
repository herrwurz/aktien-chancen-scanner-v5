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
    channel_limit: int = CHANNEL_LIMIT
    index_payload_sha256: str | None = None
    channel_counts: dict[str, int] = Field(default_factory=dict)
    channel_matched_before_limit: dict[str, int] = Field(default_factory=dict)
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
            and clue.category in {"business", "products", "technologies", "market_position"}
        }
    )
    if text:
        channels["text"] = CandidateQuery(text=" ".join(text))
    return channels


def _structured_score(identity, clues, present_channels, confirmed_markers):
    score = 0
    sectors = _values(clues, "sectors")
    countries = _values(clues, "countries")
    stock_ids = _values(clues, "identifier")
    if sectors:
        score += 20 if identity.sector in sectors else (-25 if identity.sector else 0)
    if countries:
        score += 8 if identity.country in countries else (-25 if identity.country else 0)
    if "event" in present_channels and any(
        marker.startswith("event:") for marker in confirmed_markers
    ):
        score += 25
    identity_values = {identity.wkn, identity.isin, identity.ticker}
    if stock_ids and any(value in identity_values for value in stock_ids):
        score += 100
    if "text" in present_channels:
        score += 3
    return score


def _empty_retrieval_status(*, visible_universe_size: int, identifier_miss: bool) -> str:
    if identifier_miss or visible_universe_size <= 0:
        return "not_in_universe"
    return "retrieval_missed"


def retrieve_candidates(index, clues: list[AtomicClue], *, as_of, limit=50) -> RetrievalReport:
    if not 1 <= limit <= 50:
        raise ValueError("candidate limit must be between 1 and 50")
    queries = _queries(clues)
    stock_ids = _values(clues, "identifier")
    if not queries and not stock_ids:
        return RetrievalReport(
            status="insufficiently_constrained",
            candidates=[],
            channel_limit=CHANNEL_LIMIT,
        )
    records = {}
    full_size = visible_size = matched = 0
    payload_sha = None
    channel_counts = {}
    channel_matched = {}
    warnings = []
    identifier_miss = False
    if stock_ids and hasattr(index, "market_universe"):
        universe = list(index.market_universe(as_of=as_of))
        visible_size = max(visible_size, len(universe))
        full_size = max(full_size, len(universe))
        exact = [
            identity
            for identity in universe
            if any(value in {identity.wkn, identity.isin, identity.ticker} for value in stock_ids)
        ]
        channel_counts["identifier"] = min(len(exact), CHANNEL_LIMIT)
        channel_matched["identifier"] = len(exact)
        matched += len(exact)
        if not exact:
            identifier_miss = True
            warnings.append("explicit_stock_identifier_absent_from_visible_universe")
        for rank, identity in enumerate(exact[:CHANNEL_LIMIT], 1):
            asset_id = stable_asset_id(identity)
            records[asset_id] = {
                "identity": identity,
                "ranks": {"identifier": rank},
                "confirmed": {"identifier:exact"},
            }
        if identifier_miss and not queries:
            return RetrievalReport(
                status="not_in_universe",
                candidates=[],
                full_universe_size=full_size,
                visible_universe_size=visible_size,
                matched_before_limit=matched,
                channel_limit=CHANNEL_LIMIT,
                channel_counts=channel_counts,
                channel_matched_before_limit=channel_matched,
                coverage_warnings=sorted(set(warnings)),
            )
    for channel, query in sorted(queries.items()):
        batch = index.candidates(query, as_of=as_of, limit=CHANNEL_LIMIT)
        full_size = max(full_size, batch.full_universe_size)
        visible_size = max(visible_size, batch.visible_universe_size)
        matched += batch.matched_before_limit
        channel_matched[channel] = batch.matched_before_limit
        payload_sha = payload_sha or batch.index_payload_sha256
        warnings.extend(batch.coverage_warnings)
        channel_counts[channel] = len(batch.candidates)
        if batch.matched_before_limit > CHANNEL_LIMIT:
            warnings.append(f"channel_{channel}_truncated_at_{CHANNEL_LIMIT}")
        for rank, hit in enumerate(batch.candidates, 1):
            asset_id = stable_asset_id(hit.identity)
            row = records.setdefault(
                asset_id, {"identity": hit.identity, "ranks": {}, "confirmed": set()}
            )
            row["ranks"][channel] = rank
            row["confirmed"].update(hit.confirmed)
    candidates, exclusions = [], []
    for asset_id, row in records.items():
        identity = row["identity"]
        if identity.asset_type != "stock" or identity.instrument_type in {"fund", "other"}:
            exclusions.append(
                RetrievalExclusion(
                    asset_id=asset_id,
                    name=identity.name,
                    reason="known_non_stock_instrument",
                )
            )
            continue
        ranks = row["ranks"]
        rrf_score = sum(round(1_000 / (RRF_K + rank)) for rank in ranks.values())
        structured = _structured_score(identity, clues, set(ranks), row["confirmed"])
        candidates.append(
            RetrievalCandidate(
                asset_id=asset_id,
                identity=identity,
                rrf_score=rrf_score,
                structured_score=structured,
                total_score=rrf_score + structured,
                channel_ranks=ranks,
                uncertainties=(
                    ["instrument_type_unverified"] if identity.instrument_type == "unknown" else []
                ),
            )
        )
    candidates.sort(key=lambda item: (-item.total_score, item.asset_id))
    limited = candidates[:limit]
    if limited:
        status = "ok"
    else:
        status = _empty_retrieval_status(
            visible_universe_size=visible_size,
            identifier_miss=identifier_miss,
        )
    return RetrievalReport(
        status=status,
        candidates=limited,
        exclusions=sorted(exclusions, key=lambda item: item.asset_id),
        full_universe_size=full_size,
        visible_universe_size=visible_size,
        matched_before_limit=matched,
        channel_limit=CHANNEL_LIMIT,
        index_payload_sha256=payload_sha,
        channel_counts=channel_counts,
        channel_matched_before_limit=channel_matched,
        coverage_warnings=sorted(set(warnings)),
    )
