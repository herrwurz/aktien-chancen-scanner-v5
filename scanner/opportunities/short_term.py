"""Deterministic short-term opportunity research; never an order decision."""

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from scanner.opportunities.catalysts import select_catalysts
from scanner.opportunities.features import compute_features
from scanner.opportunities.models import OpportunityCandidate, RiskScenario
from scanner.research import AssetIdentity


class OpportunityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_sessions: int = 250
    min_median_dollar_volume: Decimal = Decimal("1000000")
    max_stale_days: int = 5
    volume_spike_ratio: Decimal = Decimal("1.5")
    high_atr_percent: Decimal = Decimal("0.08")
    assumed_round_trip_cost_bps: Decimal = Decimal("30")


def _asset_id(identity: AssetIdentity) -> str:
    if identity.cik:
        return f"cik:{identity.cik.zfill(10)}"
    if identity.isin:
        return f"isin:{identity.isin}"
    return f"ticker:{identity.ticker or 'unknown'}"


def _unavailable(
    identity: AssetIdentity,
    gates: list[str],
    *,
    uncertainties: list[str] | None = None,
) -> OpportunityCandidate:
    return OpportunityCandidate(
        asset_id=_asset_id(identity),
        ticker=identity.ticker,
        name=identity.name,
        status="unavailable",
        score=0,
        score_reasons=[],
        selection_reasons=[],
        failed_gates=sorted(set(gates)),
        uncertainties=sorted(set(uncertainties or [])),
        features=None,
        catalysts=[],
        risk=None,
    )


def evaluate_candidate(
    identity: AssetIdentity,
    bars: list[dict[str, Any]],
    *,
    as_of: datetime,
    catalysts: Iterable[dict[str, Any]],
    benchmark_bars: list[dict[str, Any]] | None = None,
    policy: OpportunityPolicy | None = None,
) -> OpportunityCandidate:
    """Apply fail-closed gates, transparent scoring and a non-executable scenario."""

    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    policy = policy or OpportunityPolicy()
    cutoff = as_of.astimezone(UTC)
    bounded = [row for row in bars if str(row.get("session_date", "")) <= cutoff.date().isoformat()]
    gates: list[str] = []
    if identity.asset_type != "stock":
        gates.append("non_stock")
    if identity.instrument_type == "fund":
        gates.append("fund")
    if len(bounded) < policy.min_sessions:
        gates.append("insufficient_sessions")
    if not bounded:
        gates.append("missing_prices")
    if gates:
        return _unavailable(identity, gates)

    last_date = datetime.fromisoformat(str(bounded[-1]["session_date"])).date()
    if (cutoff.date() - last_date).days > policy.max_stale_days:
        return _unavailable(identity, ["stale_price"])

    try:
        features = compute_features(
            bounded,
            signal_date=last_date,
            benchmark_bars=benchmark_bars,
        )
    except (KeyError, TypeError, ValueError):
        return _unavailable(identity, ["incomplete_provider_data"])
    if features.median_dollar_volume_20 < policy.min_median_dollar_volume:
        return _unavailable(identity, ["insufficient_liquidity"])

    selected = select_catalysts(catalysts, signal_at=cutoff)
    score = 0
    reasons: list[str] = []

    def award(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(f"{reason}:{points:+d}")

    for window, momentum, points in (
        ("5", features.momentum_5, 1),
        ("10", features.momentum_10, 1),
        ("20", features.momentum_20, 2),
    ):
        if momentum > 0:
            award(points, f"positive_momentum_{window}")
    if features.trend == "up":
        award(2, "uptrend")
    if features.volume_ratio >= policy.volume_spike_ratio:
        award(2, "volume_spike")
    if features.breakout_20:
        award(2, "breakout_20")
    for catalyst in selected:
        if catalyst.verification_status != "confirmed":
            continue
        award(
            3 if catalyst.source_type == "PRIMARY" else 1,
            f"catalyst_{catalyst.source_type.lower()}",
        )
    if features.atr_percent > policy.high_atr_percent:
        award(-2, "high_volatility")
    uncertainties: list[str] = []
    if features.benchmark_status == "unavailable":
        award(-1, "benchmark_unavailable")
        uncertainties.append("benchmark_unavailable")

    triggers: list[str] = []
    if features.volume_ratio >= policy.volume_spike_ratio:
        triggers.append("volume_spike")
    if features.breakout_20:
        triggers.append("breakout_20")
    if any(row.verification_status == "confirmed" for row in selected):
        triggers.append("confirmed_catalyst")

    reference = features.raw_reference_close
    stop = max(Decimal("0.01"), reference - features.atr_14 * Decimal("1.5"))
    target = reference + features.atr_14 * Decimal("3")
    gross_crv = (target - reference) / (reference - stop)
    risk = RiskScenario(
        reference_date=features.signal_date,
        reference_price=reference,
        stop_price=stop,
        target_price=target,
        gross_crv=gross_crv,
        assumed_round_trip_cost_bps=policy.assumed_round_trip_cost_bps,
    )
    return OpportunityCandidate(
        asset_id=_asset_id(identity),
        ticker=identity.ticker,
        name=identity.name,
        status="candidate_research" if triggers else "watch_only",
        score=score,
        score_reasons=reasons,
        selection_reasons=triggers,
        failed_gates=[],
        uncertainties=uncertainties,
        features=features,
        catalysts=selected,
        risk=risk,
    )
