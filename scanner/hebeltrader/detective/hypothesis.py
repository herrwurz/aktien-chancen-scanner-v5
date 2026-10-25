"""Usable Top-3 hypothesis decisions, separate from strict likely_candidate."""

from .verification import (
    DetectiveDecision,
    VerifiedCandidate,
    _viable_candidates,
    decide,
)

HYPOTHESIS_FAILURES = {
    "insufficiently_constrained",
    "not_in_universe",
    "retrieval_missed",
    "all_candidates_contradicted",
}


def hypothesis_reasons(candidate: VerifiedCandidate) -> list[str]:
    reasons = []
    for clue_id in candidate.confirmed_clue_ids:
        reasons.append(f"confirmed:{clue_id}")
    for category in candidate.confirmed_categories:
        reasons.append(f"category:{category}")
    if candidate.retrieval_score:
        reasons.append(f"retrieval_score:{candidate.retrieval_score}")
    for item in candidate.uncertainties:
        reasons.append(f"uncertainty:{item}")
    return reasons


def decide_hypothesis(
    candidates: list[VerifiedCandidate],
    retrieval_status: str,
    *,
    analysis_mode: str,
) -> DetectiveDecision:
    """Return hypothesis_top3 when any viable candidates exist; else unresolved."""
    if analysis_mode != "hypothesis":
        return decide(candidates, retrieval_status)

    strict = decide(candidates, retrieval_status)
    if strict.status == "likely_candidate":
        return strict

    if retrieval_status == "insufficiently_constrained":
        return DetectiveDecision(status="unresolved", reason="insufficiently_constrained")
    if retrieval_status in {"not_in_universe", "retrieval_missed"} and not candidates:
        return DetectiveDecision(status="unresolved", reason=retrieval_status)
    if not candidates:
        reason = (
            "retrieval_missed"
            if retrieval_status in {"unresolved", "retrieval_missed"}
            else "evidence_missing"
        )
        return DetectiveDecision(status="unresolved", reason=reason)
    if all(candidate.hard_contradictions for candidate in candidates):
        return DetectiveDecision(status="unresolved", reason="all_candidates_contradicted")

    viable = _viable_candidates(candidates)
    if not viable:
        return DetectiveDecision(status="unresolved", reason="all_candidates_contradicted")

    # Prefer candidates with any confirmed clue or positive evidence/retrieval score.
    # selected_asset_id stays None: Top-3 are peer hypotheses, not a single winner.
    return DetectiveDecision(
        status="hypothesis_top3",
        reason="top_hypothesis_candidates_require_manual_review",
        selected_asset_id=None,
        score_is_probability=False,
        requires_manual_review=True,
    )


def select_hypothesis_candidates(
    candidates: list[VerifiedCandidate],
    decision: DetectiveDecision,
) -> list[VerifiedCandidate]:
    if decision.status == "hypothesis_top3":
        viable = _viable_candidates(candidates)
        ranked = [
            row
            for row in viable
            if row.confirmed_clue_ids or row.evidence_score > 0 or row.retrieval_score > 0
        ] or viable
        return ranked[:3]
    if decision.status == "likely_candidate" and decision.selected_asset_id:
        ordered = sorted(
            candidates,
            key=lambda row: (
                bool(row.hard_contradictions),
                -row.evidence_score,
                -row.retrieval_score,
                row.asset_id,
            ),
        )
        return ordered[:3]
    if decision.status == "unclear":
        return _viable_candidates(candidates)[:3]
    return []
