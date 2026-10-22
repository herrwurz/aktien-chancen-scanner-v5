"""Offline, independent evidence inventory; never an outcome or training label."""

import hashlib
import re
from collections import Counter
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from scanner.hebeltrader.backtest_availability import (
    PUBLICATION_ZONE,
    entry_policy,
    publication_evidence,
)
from scanner.hebeltrader.backtest_report import _availability, aware, document_rules, fingerprint
from scanner.hebeltrader.identity import LocalIdentityProvider
from scanner.hebeltrader.models import Document, HistoricalRecommendation, Publication

VERSION = "hebel-coverage-v1.3"
STAGES = (
    "publication_evidenced",
    "verified_availability",
    "instrument_identity_verified",
    "rules_documented",
    "market_history_sufficient",
    "modeled_entry_executable",
    "derivative_bid_ask_verified",
)
VALUES = (
    "stock_name",
    "stock_wkn",
    "stock_isin",
    "stock_currency",
    "stock_price",
    "stock_target1",
    "stock_target2",
    "stock_stop1",
    "stock_stop2",
    "derivative_wkn",
    "derivative_isin",
    "product_type",
    "maturity_date",
    "term_text",
)


def rule_candidates(doc, rec):
    """Show literal source context, never automatically approve its meaning."""
    pages = {
        e.get("page")
        for items in rec.evidence.values()
        if isinstance(items, list)
        for e in items
        if isinstance(e, dict)
    }
    candidates = []
    for page in doc.pages:
        lines = page.get("text", "").splitlines()
        seen = set()
        for index, line in enumerate(lines):
            if not re.search(
                r"stopp?|stop|kursziel|target|teilverkauf|hälfte|50\s*%|handelstag|kalendertag|\b\d+\s*tage",
                line,
                re.I,
            ):
                continue
            quote = "\n".join(lines[max(0, index - 1) : index + 2])
            if quote in seen:
                continue
            seen.add(quote)
            candidates.append(
                dict(
                    page=page["number"],
                    quote=quote[:1500],
                    truncated=len(quote) > 1500,
                    recommendation_page=page["number"] in pages,
                    requires_manual_review=True,
                    verified=False,
                )
            )
            if len(seen) >= 30:
                break
    return candidates or [
        dict(
            page=p.get("number"),
            quote=None,
            requires_manual_review=True,
            verified=False,
            reason="no_rule_phrase_found",
        )
        for p in doc.pages
    ]


def stage(reasons=(), **audit):
    reasons = sorted(set(reasons))
    return dict(status="complete" if not reasons else "incomplete", reasons=reasons, **audit)


def _level_reasons(rec):
    reasons = []
    names = ("stock_stop1", "stock_target1", "stock_target2")
    for name in names:
        value = getattr(rec, name)
        if value is None:
            reasons.append("missing_value:" + name)
        elif not rec.evidence.get(name):
            reasons.append("unverified_value:" + name)
        else:
            try:
                if not Decimal(str(value)).is_finite() or Decimal(str(value)) <= 0:
                    reasons.append("invalid_value:" + name)
            except (InvalidOperation, ValueError):
                reasons.append("invalid_value:" + name)
    currency = rec.stock_currency
    if not currency or not rec.evidence.get("stock_currency"):
        reasons.append("missing_price_currency_evidence")
    for name in names:
        for evidence in rec.evidence.get(name, []):
            units = re.search(r"(EUR|€|USD|\$|GBP)\s*$", evidence.get("raw", ""))
            if units and {"€": "EUR", "$": "USD"}.get(units[1], units[1]) != currency:
                reasons.append("conflicting_price_currency:" + name)
    for flag in rec.flags:
        if flag.get("field") in names and flag.get("code") in {
            "invalid_value",
            "conflicting_values",
        }:
            reasons.append("unverified_value:" + flag["field"])
    return reasons


def _entry_reasons(rec, bars):
    if not bars:
        return ["no_complete_entry_session"]
    try:
        stop, t1, t2 = (
            Decimal(str(getattr(rec, name)))
            for name in ("stock_stop1", "stock_target1", "stock_target2")
        )
        if not 0 < stop < bars[0].open < t1 < t2:
            return ["entry_outside_stop_target_range"]
    except (InvalidOperation, ValueError, TypeError):
        return ["missing_or_invalid_price_levels"]
    return []


def build_coverage(
    session,
    mapping,
    rule_specs,
    *,
    as_of,
    run_at,
    bars_dir=None,
    expected_count=118,
    analysis_mode="research",
    identity_provider=None,
    market_provider=None,
):
    if not aware(as_of) or not aware(run_at) or as_of > run_at:
        raise ValueError("Aware historical as_of and run_at required")
    if (
        analysis_mode not in {"research", "verified"}
        or type(expected_count) is not int
        or expected_count < 1
    ):
        raise ValueError("Invalid coverage configuration")
    identity_provider = identity_provider or LocalIdentityProvider(mapping)
    if market_provider is None and bars_dir is not None:
        from scanner.hebeltrader.market_snapshot import SnapshotStockProvider

        market_provider = SnapshotStockProvider(bars_dir)
    results = []
    with session.no_autoflush:
        query = (
            select(HistoricalRecommendation, Document)
            .join(Document, HistoricalRecommendation.document_sha == Document.sha256)
            .order_by(Document.sha256, HistoricalRecommendation.ordinal)
        )
        for rec, doc in session.execute(query):
            row = dict(
                recommendation_key=f"{doc.sha256}:{rec.ordinal}",
                document_sha=doc.sha256,
                ordinal=rec.ordinal,
                recommendation_id=rec.id,
                publication_date=doc.publication_date.isoformat() if doc.publication_date else None,
                publication_evidence=publication_evidence(doc),
                original_sha_valid=hashlib.sha256(bytes(doc.original_pdf)).hexdigest()
                == doc.sha256,
                review_status=doc.review_status,
                revision_conflict=doc.revision_conflict,
                available_at=doc.verified_available_at.isoformat()
                if doc.verified_available_at
                else None,
                availability_evidence=doc.availability_evidence,
                values={
                    k: str(getattr(rec, k)) if getattr(rec, k) is not None else None for k in VALUES
                },
                quality_flags=dict(document=doc.flags, recommendation=rec.flags),
                rule_candidates=rule_candidates(doc, rec),
                training_eligible=False,
                hypothetical=True,
                stages={},
            )
            stages = row["stages"]
            pub_reasons = [] if row["publication_evidence"] else ["unverified_publication_date"]
            if not row["original_sha_valid"]:
                pub_reasons.append("original_hash_mismatch")
            stages["publication_evidenced"] = stage(pub_reasons)
            selected = session.get(Publication, doc.publication_id) if doc.publication_id else None
            strict_reason = _availability(doc, as_of, selected.selected_sha if selected else None)
            stages["verified_availability"] = stage([strict_reason] if strict_reason else [])
            baseline = (
                datetime.combine(doc.publication_date, time.min, PUBLICATION_ZONE)
                if doc.publication_date
                else None
            )
            instrument = dict(wkn=rec.stock_wkn, isin=rec.stock_isin, currency=rec.stock_currency)
            resolution = identity_provider.resolve(
                instrument=instrument, start=baseline, end=as_of, reviewed_as_of=run_at
            )
            if not rec.stock_wkn and not rec.stock_isin:
                resolution.issues.append("missing_stock_identifier")
            row["identity"] = dict(
                candidates=resolution.candidates,
                selected=resolution.selected,
                issues=resolution.issues,
            )
            stages["instrument_identity_verified"] = stage(
                resolution.issues if resolution.selected is None else []
            )
            if (
                resolution.selected is None
                and not stages["instrument_identity_verified"]["reasons"]
            ):
                stages["instrument_identity_verified"] = stage(["identity_unverified"])
            rule, audit, rule_issue = document_rules(
                doc, rec, rule_specs.get(row["recommendation_key"]), run_at
            )
            row["rules"] = audit
            rule_reasons = [rule_issue] if rule_issue else []
            if not row["original_sha_valid"]:
                rule_reasons.append("original_hash_mismatch")
            if (
                rule
                and rule.after_target1 == "stop2"
                and (rec.stock_stop2 is None or not rec.evidence.get("stock_stop2"))
            ):
                rule_reasons.append("unverified_rule_stop2")
            stages["rules_documented"] = stage(rule_reasons)
            spec = resolution.selected or (
                resolution.candidates[0] if len(resolution.candidates) == 1 else None
            )
            cutoff, policy_reason, policy = entry_policy(
                doc, as_of, analysis_mode, strict_reason, spec.get("timezone") if spec else None
            )
            if doc.revision_conflict and strict_reason:
                policy_reason = "unresolved_revision_conflict"
            row["entry_policy"] = policy
            row["market"] = None
            row["modeled_entry_at"] = None
            # Check market coverage independently from availability, identity approval and rules.
            # Without an entry cutoff, inspect data from publication baseline only.
            inventory_start = cutoff or baseline
            market_reasons = []
            history = None
            if spec is None:
                market_reasons.append("no_unique_market_candidate")
            if market_provider is None:
                market_reasons.append("market_directory_not_supplied")
            if inventory_start is None or inventory_start >= as_of:
                market_reasons.append("market_window_unknown")
            if not market_reasons:
                try:
                    history = market_provider.load(
                        spec,
                        instrument=dict(
                            instrument,
                            currency=rec.stock_currency or spec.get("currency"),
                            levels_as_of=baseline,
                        ),
                        available_at=inventory_start,
                        as_of=as_of,
                    )
                    market_reasons.extend(history.issues)
                    retrieved = history.source.get("retrieved_at")
                    if retrieved and datetime.fromisoformat(retrieved) > run_at:
                        market_reasons.append("future_retrieval_metadata")
                    row["market"] = dict(
                        source=history.source,
                        issues=market_reasons,
                        complete_bars=len(history.bars),
                        identity_verified=resolution.selected is not None,
                        inventory_cutoff=inventory_start.isoformat(),
                    )
                except (ValueError, TypeError, KeyError, OSError):
                    market_reasons.append("invalid_market_source")
            stages["market_history_sufficient"] = stage(
                market_reasons, scope="candidate_history; identity_confirmation_is_a_separate_stage"
            )
            entry_reasons = [*pub_reasons, *_level_reasons(rec)]
            if policy_reason:
                entry_reasons.append(policy_reason)
            if resolution.selected is None:
                entry_reasons.append("entry_identity_unverified")
            if market_reasons:
                entry_reasons.append("entry_market_history_insufficient")
            if not entry_reasons:
                entry_reasons.extend(_entry_reasons(rec, history.bars if history else []))
                if not entry_reasons:
                    row["modeled_entry_at"] = history.bars[0].at.isoformat()
            stages["modeled_entry_executable"] = stage(
                entry_reasons,
                execution="hypothetical_session_open_not_a_fill",
                rules_required_for_outcomes=True,
            )
            stages["derivative_bid_ask_verified"] = stage(["derivative_bid_ask_unavailable"])
            row["blockers"] = sorted({reason for s in stages.values() for reason in s["reasons"]})
            results.append(row)
    summary = {
        name: dict(
            complete=sum(r["stages"][name]["status"] == "complete" for r in results),
            total=len(results),
        )
        for name in STAGES
    }
    actions = [
        dict(
            priority=10 * (STAGES.index(name) + 1),
            recommendation_key=r["recommendation_key"],
            document_sha=r["document_sha"],
            ordinal=r["ordinal"],
            stage=name,
            reason=reason,
        )
        for r in results
        for name in STAGES
        for reason in r["stages"][name]["reasons"]
    ]
    actions.sort(key=lambda a: (a["priority"], a["recommendation_key"], a["reason"]))
    counts = Counter(reason for r in results for reason in r["blockers"])
    repeated = Counter(r["values"]["stock_wkn"] for r in results if r["values"]["stock_wkn"])
    return dict(
        version=VERSION,
        mode="read_only_offline_inventory",
        analysis_mode=analysis_mode,
        as_of=as_of.isoformat(),
        generated_at=run_at.isoformat(),
        count=len(results),
        expected_count=expected_count,
        warnings=[] if len(results) == expected_count else ["recommendation_count_mismatch"],
        summary=summary,
        blocker_counts=dict(sorted(counts.items())),
        field_completeness={
            k: dict(
                present=sum(r["values"][k] is not None for r in results),
                missing=sum(r["values"][k] is None for r in results),
            )
            for k in VALUES
        },
        repeated_stock_wkn={k: v for k, v in sorted(repeated.items()) if v > 1},
        mapping_sha256=fingerprint(mapping),
        rules_sha256=fingerprint(rule_specs),
        success_rate=None,
        results=results,
        manual_review=actions,
    )
