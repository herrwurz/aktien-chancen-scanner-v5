"""Read-only, source-bound backtest orchestration. No archive-location queries."""

import hashlib
import json
from collections import Counter
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select

from scanner.hebeltrader.backtest import VERSION, Rules, simulate_stock
from scanner.hebeltrader.backtest_availability import entry_policy
from scanner.hebeltrader.models import Document, HistoricalRecommendation, Publication


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def document_rules(doc, rec, spec, run_at):
    """A human interpretation must cite the exact source; never infer from labels."""
    if not spec:
        return None, None, "missing_documented_rules"
    try:
        if spec.get("conditional_loss_exit") is not None or spec.get("target2_sale") is not None:
            # Preparation proposals are not supported by the V1.3 execution engine.
            raise ValueError
        if (
            spec.get("requires_manual_review")
            or spec.get("review_status", "approved") != "approved"
        ):
            raise ValueError
        if spec["document_sha"] != doc.sha256 or spec["ordinal"] != rec.ordinal:
            raise ValueError
        if not isinstance(spec["reviewer"], str) or not spec["reviewer"].strip():
            raise ValueError
        reviewed = datetime.fromisoformat(spec["reviewed_at"])
        if not aware(reviewed) or reviewed > run_at:
            raise ValueError
        if Decimal(str(spec["partial_fraction"])) != Decimal("0.5"):
            raise ValueError
        if spec["after_target1"] not in {"unchanged", "entry", "stop2"}:
            raise ValueError
        expiry = spec.get("exit_after")
        required = {"partial_fraction", "after_target1"}
        if expiry is not None:
            if (
                type(expiry["days"]) is not int
                or expiry["days"] <= 0
                or expiry["unit"] not in {"calendar_days", "trading_sessions"}
            ):
                raise ValueError
            required.add("exit_after")
        covered = set()
        for item in spec["evidence"]:
            page = next((p for p in doc.pages if p["number"] == item["page"]), None)
            quote = item["quote"]
            if not isinstance(quote, str) or not quote.strip() or page is None:
                raise ValueError
            # Whitespace/layout differences do not change the literal cited words.
            if " ".join(quote.split()) not in " ".join(page.get("text", "").split()):
                raise ValueError
            covered.update(item["fields"])
        if not required.issubset(covered):
            raise ValueError
        rules = Rules(
            spec["after_target1"],
            expiry["days"] if expiry else None,
            expiry["unit"] if expiry else None,
        )
        return rules, dict(spec, sha256=fingerprint(spec)), None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None, None, "unverified_rule_evidence"


def _availability(doc, as_of, selected_sha=None):
    if doc.review_status in {"rejected", "superseded"}:
        return "excluded_review_status"
    if doc.extraction_status != "extracted":
        return "failed_extraction"
    if doc.publication_date is None:
        return "missing_publication_date"
    available = doc.verified_available_at
    if (
        not aware(available)
        or not doc.availability_evidence
        or not doc.availability_evidence.strip()
    ):
        return "unverified_availability"
    earliest = datetime.combine(doc.publication_date, time.min, ZoneInfo("Europe/Berlin"))
    if available < earliest:
        return "availability_precedes_publication"
    if available >= as_of:
        return "not_available_as_of"
    if doc.revision_conflict and (doc.review_status != "approved" or selected_sha != doc.sha256):
        return "unresolved_revision_conflict"
    return None


def build_report(
    session, provider, mapping, rule_specs, *, as_of, run_at, analysis_mode="verified"
):
    if analysis_mode not in {"verified", "research"}:
        raise ValueError("analysis_mode must be verified or research")
    if not aware(as_of) or not aware(run_at) or as_of > run_at:
        raise ValueError("as_of and run_at must be aware and as_of must not be future")
    results = []
    with session.no_autoflush:
        rows = session.execute(
            select(HistoricalRecommendation, Document)
            .join(Document, HistoricalRecommendation.document_sha == Document.sha256)
            .order_by(Document.sha256, HistoricalRecommendation.ordinal)
        )
        for rec, doc in rows:
            selected = session.get(Publication, doc.publication_id) if doc.publication_id else None
            source_verified = bool(
                doc.review_status == "approved" and selected and selected.selected_sha == doc.sha256
            )
            row = dict(
                recommendation_id=rec.id,
                ordinal=rec.ordinal,
                document_sha=doc.sha256,
                publication_date=str(doc.publication_date) if doc.publication_date else None,
                available_at=doc.verified_available_at.isoformat()
                if doc.verified_available_at
                else None,
                availability_evidence=doc.availability_evidence,
                review_status=doc.review_status,
                source_verified=source_verified,
                training_eligible=False,
                analysis_mode=analysis_mode,
                hypothetical=True,
                modeled_entry_at=None,
                method_version=VERSION,
                instrument=dict(
                    wkn=rec.stock_wkn, isin=rec.stock_isin, currency=rec.stock_currency
                ),
                published_stock_quote=str(rec.stock_price) if rec.stock_price is not None else None,
                observation_window=dict(start=None, end=as_of.isoformat()),
                source=None,
                rules=None,
                data_issues=[],
                result=None,
                derivative=dict(
                    status="derivative_unverified",
                    wkn=rec.derivative_wkn,
                    isin=rec.derivative_isin,
                    product_type=rec.product_type,
                    maturity_date=str(rec.maturity_date) if rec.maturity_date else None,
                    term_text=rec.term_text,
                    realized_return_pct=None,
                    reason="missing_timestamped_derivative_bid_ask",
                ),
            )
            strict_reason = _availability(doc, as_of, selected.selected_sha if selected else None)
            spec = mapping.get(rec.stock_wkn) or mapping.get(rec.stock_isin)
            cutoff, reason, policy_audit = entry_policy(
                doc,
                as_of,
                analysis_mode,
                strict_reason,
                spec.get("timezone") if isinstance(spec, dict) else None,
            )
            row.update(policy_audit)
            row["input_sha256"] = fingerprint(
                dict(
                    document_sha=doc.sha256,
                    ordinal=rec.ordinal,
                    levels={
                        k: getattr(rec, k)
                        for k in ("stock_target1", "stock_target2", "stock_stop1", "stock_stop2")
                    },
                    evidence=rec.evidence,
                    available_at=row["available_at"],
                    analysis_mode=analysis_mode,
                    entry_policy=policy_audit,
                )
            )
            row["source_verified"] = (
                analysis_mode == "verified" and source_verified and strict_reason is None
            )
            if analysis_mode == "research" and doc.revision_conflict and strict_reason is not None:
                reason = "unresolved_revision_conflict"
            if not reason and hashlib.sha256(bytes(doc.original_pdf)).hexdigest() != doc.sha256:
                reason = "original_hash_mismatch"
            if not reason:
                levels = {"stock_target1", "stock_target2", "stock_stop1"}
                if any(not rec.evidence.get(k) for k in levels) or any(
                    f.get("field") in levels
                    and f.get("code") in {"invalid_value", "conflicting_values"}
                    for f in rec.flags
                ):
                    reason = "unverified_price_levels"
            if not reason:
                rule, audit, reason = document_rules(
                    doc, rec, rule_specs.get(f"{doc.sha256}:{rec.ordinal}"), run_at
                )
                row["rules"] = audit
                if (
                    not reason
                    and rule.after_target1 == "stop2"
                    and not rec.evidence.get("stock_stop2")
                ):
                    reason = "unverified_price_levels"
            if not reason:
                spec = mapping.get(rec.stock_wkn) or mapping.get(rec.stock_isin)
                if not isinstance(spec, dict):
                    reason = "data_unavailable"
                    row["data_issues"] = ["unmapped_stock_instrument"]
                else:
                    row["instrument"]["levels_as_of"] = datetime.combine(
                        doc.publication_date, time.min, ZoneInfo("Europe/Berlin")
                    ).isoformat()
                    history = provider.load(
                        spec,
                        instrument=row["instrument"],
                        available_at=cutoff,
                        as_of=as_of,
                    )
                    row["source"] = history.source
                    row["data_issues"] = history.issues
                    retrieved = history.source.get("retrieved_at")
                    try:
                        if retrieved and datetime.fromisoformat(retrieved) > run_at:
                            history.issues.append("future_retrieval_metadata")
                    except (ValueError, TypeError):
                        if "missing_metadata" not in history.issues:
                            history.issues.append("missing_metadata")
                    if history.issues:
                        reason = "data_unavailable"
                    else:
                        if history.bars:
                            row["modeled_entry_at"] = history.bars[0].at.isoformat()
                        row["result"] = simulate_stock(
                            available_at=cutoff,
                            bars=history.bars,
                            target1=rec.stock_target1,
                            target2=rec.stock_target2,
                            stop1=rec.stock_stop1,
                            stop2=rec.stock_stop2,
                            horizon=as_of,
                            rules=rule,
                        )
                        if history.bars:
                            row["observation_window"].update(
                                start=history.bars[0].at.isoformat(),
                                last_completed_bar=history.bars[-1].end_at.isoformat(),
                            )
            if row["result"] is None:
                row["result"] = dict(
                    status="unknown",
                    reason=reason,
                    events=[],
                    realized_return_pct=None,
                    modeled_return_pct=None,
                )
            row["model_assumptions"] = dict(
                entry=(
                    "first_complete_session_after_publication_day"
                    if analysis_mode == "research"
                    else "first_complete_session_open_strictly_after_verified_availability"
                ),
                historical_availability_claimed=analysis_mode == "verified"
                and strict_reason is None,
                execution="hypothetical_not_observed",
                target1_fraction="0.5",
                spread=None,
                fees=None,
                slippage=None,
                returns="gross_model_only",
                training="never_promoted_by_backtest",
            )
            results.append(row)
    counts = Counter(r["result"]["status"] for r in results)
    reasons = Counter(r["result"].get("reason") for r in results if r["result"].get("reason"))
    issues = Counter(i for r in results for i in r["data_issues"])
    covered = sum(r["source"] is not None and not r["data_issues"] for r in results)
    return dict(
        method_version=VERSION,
        mode="read_only",
        analysis_mode=analysis_mode,
        as_of=as_of.isoformat(),
        generated_at=run_at.isoformat(),
        count=len(results),
        counts=dict(sorted(counts.items())),
        coverage=dict(
            total=len(results),
            market_data_complete=covered,
            market_data_fraction=str(Decimal(covered) / len(results)) if results else None,
            source_verified=sum(r["source_verified"] for r in results),
        ),
        missing_data=dict(
            reasons=dict(sorted(reasons.items())), issues=dict(sorted(issues.items()))
        ),
        success_rate=None,
        success_rate_reason="no_verified_executions_or_net_returns",
        mapping_sha256=fingerprint(mapping),
        rules_sha256=fingerprint(rule_specs),
        results=results,
    )
