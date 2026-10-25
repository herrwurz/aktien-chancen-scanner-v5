"""Point-in-time Stage-B evidence verification and uncalibrated decisions."""

import hashlib

from pydantic import BaseModel, Field

from scanner.research import EvidenceRecord

from .retrieval import RetrievalReport
from .schemas import AtomicClue

PRIMARY_KINDS = {"issuer", "regulatory", "product_document"}
SUPPORTED_FACT_GROUPS = {"sectors", "countries", "events", "fact_claims"}
HARD_CONTRADICTION_GROUPS = {"countries", "sectors", "financial_metric", "identifier"}


class EvidenceCell(BaseModel):
    clue_id: str
    status: str
    evidence_cluster_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class EvidenceCluster(BaseModel):
    cluster_id: str
    origin_id: str
    source_ids: list[str]
    source_kinds: list[str]
    primary: bool
    available_at: str


class VerifiedCandidate(BaseModel):
    asset_id: str
    identity: dict
    retrieval_score: int
    evidence_score: int
    evidence_matrix: list[EvidenceCell]
    evidence_clusters: list[EvidenceCluster]
    confirmed_clue_ids: list[str]
    contradicted_clue_ids: list[str]
    unknown_clue_ids: list[str]
    confirmed_categories: list[str]
    hard_contradictions: list[str]
    excluded_source_ids: list[str]
    eligible_evidence: list[dict] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class DetectiveDecision(BaseModel):
    status: str
    reason: str
    selected_asset_id: str | None = None
    score_is_probability: bool = False
    requires_manual_review: bool = True


def _eligible(records, as_of):
    included, excluded = [], []
    for record in records:
        record = EvidenceRecord.model_validate(record)
        timestamps = (
            record.published_at,
            record.effective_at,
            record.source_available_at,
        )
        if record.source_available_at is None or any(
            value > as_of for value in timestamps if value
        ):
            excluded.append(record.source_id)
        else:
            included.append(record)
    return included, sorted(excluded)


def _cluster(records):
    groups = []
    for record in records:
        origin = str(record.facts.get("origin_id") or record.source_id)
        matching = [
            group
            for group in groups
            if origin in group["origins"] or record.content_sha256 in group["hashes"]
        ]
        if matching:
            group = matching[0]
            for extra in matching[1:]:
                group["rows"].extend(extra["rows"])
                group["origins"].update(extra["origins"])
                group["hashes"].update(extra["hashes"])
                groups.remove(extra)
        else:
            group = {"rows": [], "origins": set(), "hashes": set()}
            groups.append(group)
        group["rows"].append(record)
        group["origins"].add(origin)
        group["hashes"].add(record.content_sha256)
    clusters = []
    source_to_cluster = {}
    groups.sort(key=lambda group: sorted(group["origins"]))
    for group in groups:
        rows = group["rows"]
        origins = sorted(group["origins"])
        fingerprint = "|".join([*origins, *sorted(group["hashes"])])
        cluster_id = hashlib.sha256(fingerprint.encode()).hexdigest()
        for row in rows:
            source_to_cluster[row.source_id] = cluster_id
        clusters.append(
            EvidenceCluster(
                cluster_id=cluster_id,
                origin_id=origins[0],
                source_ids=sorted(row.source_id for row in rows),
                source_kinds=sorted({row.source_kind for row in rows}),
                primary=any(row.source_kind in PRIMARY_KINDS for row in rows),
                available_at=max(row.source_available_at for row in rows).isoformat(),
            )
        )
    return clusters, source_to_cluster


def _cell(clue, records, source_to_cluster, identity):
    if clue.category == "identifier":
        values = {identity.wkn, identity.isin, identity.ticker}
        if clue.instrument_scope != "stock":
            return EvidenceCell(
                clue_id=clue.clue_id, status="unknown", reason="non_stock_identifier"
            )
        return EvidenceCell(
            clue_id=clue.clue_id,
            status="confirmed" if clue.value in values else "contradicted",
            reason="historically_available_identity",
        )
    if clue.category not in SUPPORTED_FACT_GROUPS:
        return EvidenceCell(
            clue_id=clue.clue_id,
            status="unknown",
            reason="unsupported_by_archived_sources",
        )
    supporting, observed = [], set()
    for record in records:
        values = set(record.facts.get(clue.category, []))
        observed.update(values)
        if (clue.value or clue.normalized) in values:
            supporting.append(source_to_cluster[record.source_id])
    if supporting:
        return EvidenceCell(
            clue_id=clue.clue_id,
            status="contradicted" if clue.polarity == "negated" else "confirmed",
            evidence_cluster_ids=sorted(set(supporting)),
        )
    if observed and clue.category in {"countries", "sectors"}:
        return EvidenceCell(
            clue_id=clue.clue_id,
            status="confirmed" if clue.polarity == "negated" else "contradicted",
            reason="archived_value_mismatch",
        )
    if clue.category in {"countries", "sectors"}:
        field = "country" if clue.category == "countries" else "sector"
        identity_value = getattr(identity, field)
        if identity_value is not None:
            matched = (clue.value or clue.normalized) == identity_value
            return EvidenceCell(
                clue_id=clue.clue_id,
                status=("confirmed" if matched != (clue.polarity == "negated") else "contradicted"),
                reason="historically_available_identity",
            )
    return EvidenceCell(clue_id=clue.clue_id, status="unknown", reason="no_concrete_evidence")


def verify_candidates(
    retrieval: RetrievalReport,
    clues: list[AtomicClue],
    evidence_loader,
    as_of,
) -> list[VerifiedCandidate]:
    verified = []
    for candidate in retrieval.candidates:
        records, excluded = _eligible(evidence_loader(candidate.identity), as_of)
        clusters, source_to_cluster = _cluster(records)
        matrix = [_cell(clue, records, source_to_cluster, candidate.identity) for clue in clues]
        by_id = {clue.clue_id: clue for clue in clues}
        confirmed = [cell.clue_id for cell in matrix if cell.status == "confirmed"]
        contradicted = [cell.clue_id for cell in matrix if cell.status == "contradicted"]
        unknown = [cell.clue_id for cell in matrix if cell.status == "unknown"]
        hard = [
            clue_id
            for clue_id in contradicted
            if by_id[clue_id].category in HARD_CONTRADICTION_GROUPS
        ]
        evidence_score = candidate.total_score + len(confirmed) * 12 - len(hard) * 30
        verified.append(
            VerifiedCandidate(
                asset_id=candidate.asset_id,
                identity=candidate.identity.model_dump(mode="json"),
                retrieval_score=candidate.total_score,
                evidence_score=evidence_score,
                evidence_matrix=matrix,
                evidence_clusters=clusters,
                confirmed_clue_ids=confirmed,
                contradicted_clue_ids=contradicted,
                unknown_clue_ids=unknown,
                confirmed_categories=sorted({by_id[item].category for item in confirmed}),
                hard_contradictions=hard,
                excluded_source_ids=excluded,
                eligible_evidence=[record.model_dump(mode="json") for record in records[:8]],
                uncertainties=candidate.uncertainties,
            )
        )
    return sorted(verified, key=lambda row: (-row.evidence_score, row.asset_id))


def decide(candidates: list[VerifiedCandidate], retrieval_status: str) -> DetectiveDecision:
    if retrieval_status in {"missing_publication_time", "insufficiently_constrained"}:
        return DetectiveDecision(status="unresolved", reason=retrieval_status)
    if not candidates or not candidates[0].confirmed_clue_ids:
        return DetectiveDecision(status="unresolved", reason="insufficient_evidence")
    leader = candidates[0]
    margin = (
        leader.evidence_score - candidates[1].evidence_score
        if len(candidates) > 1
        else leader.evidence_score
    )
    independent_clusters = {
        cluster_id
        for cell in leader.evidence_matrix
        if cell.status == "confirmed"
        for cluster_id in cell.evidence_cluster_ids
    }
    primary_clusters = {
        cluster.cluster_id for cluster in leader.evidence_clusters if cluster.primary
    }
    likely = all(
        (
            len(leader.confirmed_clue_ids) >= 3,
            len(leader.confirmed_categories) >= 2,
            len(independent_clusters) >= 2,
            bool(independent_clusters & primary_clusters),
            not leader.hard_contradictions,
            margin >= 20,
        )
    )
    return DetectiveDecision(
        status="likely_candidate" if likely else "unclear",
        reason=(
            "frozen_evidence_thresholds_met"
            if likely
            else "evidence_present_but_confirmation_thresholds_not_met"
        ),
        selected_asset_id=leader.asset_id if likely else None,
    )
