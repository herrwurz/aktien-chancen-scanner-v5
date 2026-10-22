"""Read-only, source-bound JNJ pilot; absence of inputs is a reportable result."""

from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .backtest import simulate_stock
from .backtest_availability import PUBLICATION_ZONE, entry_policy, publication_evidence
from .backtest_report import _availability, document_rules
from .coverage import _level_reasons, rule_candidates
from .eodhd import canonical, sha
from .eodhd_adapter import EodhdStockProvider
from .historical_identity import ReviewedIdentityProvider
from .market_snapshot import _credentials
from .models import Document, HistoricalRecommendation, Publication
from .pilot_market import approved, calendar_supported, price_path_metrics, reconcile_history
from .rule_assistant import suggest_rules

JNJ_SHA = "0223ed07b672b4f02379cff6477d24290de3801d89179a0fa4c0e9c2a44268fc"
EXPIRY = date(2026, 1, 16)
CONTINUATION = date(2026, 10, 21)
CANDIDATE = dict(
    wkn="853260",
    isin="US4781601046",
    symbol="JNJ.US",
    ticker="JNJ",
    venue="XNYS",
    currency="USD",
    timezone="America/New_York",
)
EXPECTED = dict(
    stock_wkn="853260",
    stock_currency="USD",
    stock_price="171.04",
    stock_target1="190",
    stock_target2="216",
    stock_stop1="160",
    stock_stop2="171.04",
    derivative_wkn="HS5RMP",
    derivative_currency="EUR",
    entry_price="0.17",
    derivative_target1="0.70",
    derivative_target2="2.30",
    maturity_date="2026-01-16",
)
NUMBERS = {
    k
    for k in EXPECTED
    if k
    not in {"stock_wkn", "stock_currency", "derivative_wkn", "derivative_currency", "maturity_date"}
}


def _unknown():
    return dict(
        status="unknown",
        modeled_entry=None,
        modeled_entry_at=None,
        entry_source=None,
        fully_evaluable=False,
        modeled_return_pct=None,
        realized_return_pct=None,
        events=[],
        metrics={},
        training_eligible=False,
    )


def _projection_supported(review, rules, doc, run_at):
    return bool(
        approved(review, run_at)
        and review.get("document_sha") == doc.sha256
        and review.get("ordinal") == 1
        and review.get("original_rule_scope") == "derivative"
        and review.get("model_scope") == "hypothetical_stock"
        and review.get("additional_document_rules_reviewed") is True
        and isinstance(review.get("scope_decision"), str)
        and review["scope_decision"].strip()
        and review.get("rule_spec_sha256") == sha(canonical(rules))
    )


def build_pilot_report(
    session,
    *,
    run_at,
    end_date=EXPIRY,
    analysis_mode="research",
    mapping=None,
    records=(),
    rules=None,
    bundles=(),
    market_root=None,
    raw_cache=None,
    calendar_review=None,
    projection_review=None,
    action_review=None,
    cache_dir=None,
    archive_audit=None,
    synthetic=False,
    document_sha=JNJ_SHA,
):
    if (
        run_at.utcoffset() is None
        or end_date not in {EXPIRY, CONTINUATION}
        or analysis_mode not in {"research", "verified"}
        or document_sha != JNJ_SHA
        and not synthetic
    ):
        raise ValueError("invalid pilot scope or clock")
    inputs = dict(
        mapping=mapping or {},
        records=list(records),
        rules=rules or {},
        bundles=list(bundles),
        calendar_review=calendar_review,
        projection_review=projection_review,
        action_review=action_review,
        archive_audit=archive_audit,
    )
    _credentials(inputs)
    zone = ZoneInfo("America/New_York")
    as_of = datetime.combine(end_date, time(23, 59, 59), zone)
    if as_of > run_at:
        raise ValueError("future pilot horizon")
    blockers = []
    report = dict(
        version="hebel-jnj-pilot-v1.7",
        generated_at=run_at.isoformat(),
        data_classification="synthetic"
        if synthetic
        else "local_original; vendor_inputs_not_implied",
        recommendation_key=f"{document_sha}:1",
        analysis_mode=analysis_mode,
        primary_success_metric="verified_executable_HS5RMP_bid_ask_return",
        underlying_market_data_role=(
            "context_and_separate_stock_research_only; never a derivative-price substitute"
        ),
        window=dict(
            start_date="2025-08-05",
            end_date=str(end_date),
            as_of=as_of.isoformat(),
            scope="stock_only_continuation"
            if end_date == CONTINUATION
            else "original_expiry_window",
            horizon_is_not_an_exit_rule=True,
        ),
        original_recommendation=dict(loaded=False, document_sha=document_sha, ordinal=1),
        identity=dict(
            candidate=CANDIDATE,
            status="unverified",
            selected=None,
            candidate_provenance="user supplied; not independently verified",
        ),
        historical_market_data=dict(
            status="not_supplied",
            complete_bars=0,
            missing_sessions=None,
            source=None,
            issues=["market_archive_not_supplied"],
        ),
        price_events=[],
        stock_model=_unknown(),
        derivative_observations=dict(
            status="not_available",
            events=[],
            return_pct=None,
            missing=[
                "historical_bid_ask",
                "historical_product_terms",
                "executable_liquidity",
                "costs_and_execution_model",
            ],
            stock_ohlcv_substitution=False,
            primary_pilot_instrument=True,
            product_terms=dict(
                wkn="HS5RMP",
                issuer=None,
                isin=None,
                ratio=None,
                strike=None,
                maturity_from_recommendation="2026-01-16",
                last_trading_at=None,
                settlement=None,
                verification_status="pending_original_product_document",
                requires_manual_review=True,
            ),
            quote_window=dict(start="2025-08-05", end="2026-01-16"),
            modeled_or_implied_prices_used=False,
        ),
        rule_audit=dict(original_scope="derivative", stock_scope="hypothetical_projection_only"),
        quality=dict(
            classification="blocked",
            blockers=blockers,
            uncertainties=[
                "daily_ohlc_does_not_prove_executable_transactions",
                "warrant_expiry_is_not_a_stock_exit",
                "full_intraday_drawdown_and_order_of_touches_unknown",
                "vendor_US_prices_are_not_MIC_specific_executable_quotes",
            ],
        ),
        inputs_sha256=sha(canonical(inputs)),
        openfigi_archive_audit=archive_audit,
        network_requests_during_report=0,
        database_writes=0,
        training_eligible=False,
    )

    def finish():
        report["quality"]["blockers"] = sorted(set(blockers))
        report["report_sha256"] = sha(canonical(report))
        return report

    with session.no_autoflush:
        found = session.execute(
            select(Document, HistoricalRecommendation)
            .join(
                HistoricalRecommendation, HistoricalRecommendation.document_sha == Document.sha256
            )
            .where(Document.sha256 == document_sha, HistoricalRecommendation.ordinal == 1)
        ).one_or_none()
        if found is None:
            blockers.append("original_recommendation_not_found")
            return finish()
        doc, rec = found
        source_valid = sha(bytes(doc.original_pdf)) == doc.sha256 and rec.document_sha == doc.sha256
        raw_values = {
            k: str(getattr(rec, k)) if getattr(rec, k) is not None else None for k in EXPECTED
        }
        values = dict(raw_values, stock_name=rec.stock_name, stock_isin=rec.stock_isin)
        mismatches = []
        for field, expected in EXPECTED.items():
            actual = raw_values[field]
            if field in NUMBERS and actual is not None:
                # Display-only normalization of SQLite Numeric storage noise; originals untouched.
                if abs(Decimal(actual) - Decimal(expected)) <= Decimal("0.000000000001"):
                    values[field] = expected
                else:
                    mismatches.append(field)
            elif actual != expected:
                mismatches.append(field)
        if " ".join((rec.stock_name or "").casefold().split()) != "johnson & johnson":
            mismatches.append("stock_name")
        if doc.publication_date != date(2025, 8, 5):
            mismatches.append("publication_date")
        report["original_recommendation"].update(
            loaded=True,
            original_sha_valid=source_valid,
            extractor_version=doc.extractor_version,
            values=values,
            raw_database_values=raw_values,
            publication_date=str(doc.publication_date),
            field_evidence=rec.evidence,
            mismatch_fields=mismatches,
            display_normalization="SQLite Numeric noise <=1e-12 only; original values retained",
        )
        report["rule_audit"].update(
            literal_contexts=rule_candidates(doc, rec),
            proposals=suggest_rules(doc, rec, run_at=run_at),
            additional_document_rules=(
                "must be manually reviewed; no automatic adoption or omission"
            ),
        )
        if not source_valid:
            blockers.append("original_pdf_integrity_failed")
        if mismatches:
            blockers.extend("original_value_mismatch:" + f for f in mismatches)
        if not publication_evidence(doc):
            blockers.append("publication_date_evidence_missing")
        if not source_valid or mismatches:
            return finish()
        baseline = datetime.combine(doc.publication_date, time.min, PUBLICATION_ZONE)
        selected_pub = session.get(Publication, doc.publication_id) if doc.publication_id else None
        strict_reason = _availability(
            doc, as_of, selected_pub.selected_sha if selected_pub else None
        )
        cutoff, policy_reason, policy = entry_policy(
            doc, as_of, analysis_mode, strict_reason, zone.key
        )
        report["entry_policy"] = policy
        if policy_reason:
            blockers.append(policy_reason)
        if strict_reason:
            report["quality"]["uncertainties"].append(strict_reason)
        if doc.revision_conflict and strict_reason:
            blockers.append("unresolved_revision_conflict")
        if archive_audit and archive_audit["errors"]:
            blockers.append("openfigi_archive_integrity_failed")
        resolver = ReviewedIdentityProvider(
            mapping or {}, list(records), run_at=run_at, cache_dir=cache_dir
        )
        resolution = resolver.resolve(
            instrument=dict(wkn=rec.stock_wkn, isin=rec.stock_isin, currency=rec.stock_currency),
            start=baseline,
            end=as_of,
            reviewed_as_of=run_at,
        )
        report["identity"]["manual_mapping"] = (mapping or {}).get("853260", [])
        report["identity"]["source_records"] = [
            r for r in records if r.get("query_wkn") == "853260"
        ]
        report["identity"].update(
            selected=resolution.selected, issues=resolution.issues, candidates=resolution.candidates
        )
        if resolution.selected:
            report["identity"]["status"] = "verified"
        else:
            blockers.append("historical_identity_unverified")
        rule_spec = (rules or {}).get(report["recommendation_key"])
        rule, audit, issue = document_rules(doc, rec, rule_spec, run_at)
        report["rule_audit"].update(approved_rule=audit, projection_review=projection_review)
        if issue or not rule or rule.version != "1.6":
            blockers.append(issue or "complete_v16_rules_required")
        if not _projection_supported(projection_review, rule_spec, doc, run_at):
            blockers.append("explicit_stock_projection_review_required")
        if audit and audit.get("research_assumption"):
            report["quality"]["uncertainties"].append("time_unit_is_research_interpretation")
            if analysis_mode == "verified":
                blockers.append("unverified_time_unit_interpretation")
        blockers.extend(_level_reasons(rec))
        if rule and rule.after_target1 == "stop2" and not rec.evidence.get("stock_stop2"):
            blockers.append("unverified_rule_stop2")
        if not approved(calendar_review, run_at):
            blockers.append("calendar_source_review_required")
        if len(bundles) != 1 or not market_root or not raw_cache:
            blockers.append("single_jnj_market_archive_required")
            return finish()
        bundle = bundles[0]
        spec = resolution.selected or bundle["spec"]
        if any(spec.get(k) != v for k, v in CANDIDATE.items() if k != "ticker"):
            blockers.append("jnj_market_candidate_mismatch")
            return finish()
        observation_cutoff, _, _ = entry_policy(doc, as_of, "research", strict_reason, zone.key)
        if observation_cutoff is None:
            blockers.append("observation_window_unavailable")
            return finish()
        try:
            history = EodhdStockProvider(market_root, raw_cache, list(bundles)).load(
                spec,
                instrument=dict(
                    wkn=rec.stock_wkn,
                    isin=rec.stock_isin,
                    currency=rec.stock_currency,
                    levels_as_of=baseline,
                ),
                available_at=observation_cutoff,
                as_of=as_of,
            )
            integrity = reconcile_history(
                history,
                bundle,
                market_root=market_root,
                raw_cache=raw_cache,
                cutoff=observation_cutoff,
                as_of=as_of,
                baseline=baseline,
                action_review=action_review,
                run_at=run_at,
            )
            report["historical_market_data"] = dict(
                status="archived_inputs",
                complete_bars=len(history.bars),
                source=history.source,
                calendar_review=calendar_review,
                action_review=action_review,
                **integrity,
            )
            blockers.extend(integrity["issues"])
            calendar_ok = calendar_supported(
                calendar_review, spec, raw_cache, baseline, as_of, run_at
            )
            if not calendar_ok:
                blockers.append("calendar_source_review_required")
            report["historical_market_data"]["calendar_source_verified"] = bool(calendar_ok)
            if not integrity["issues"]:
                report["observed_stock_price_path"] = price_path_metrics(history.bars)
                levels = {
                    k: getattr(rec, "stock_" + k) for k in ("target1", "target2", "stop1", "stop2")
                }
                for bar in history.bars:
                    day = bar.at.astimezone(zone).date().isoformat()
                    for name, level in levels.items():
                        if level is None or not (
                            bar.high >= level if name.startswith("target") else bar.low <= level
                        ):
                            continue
                        report["price_events"].append(
                            dict(
                                date=day,
                                level=name,
                                at_price=str(level),
                                interpretation=(
                                    "price touch; not execution; stop2 not auto-active"
                                ),
                                identity_status=report["identity"]["status"],
                                calendar_source_verified=bool(calendar_ok),
                                ohlcv={
                                    k: str(getattr(bar, k))
                                    for k in ("open", "high", "low", "close", "volume")
                                },
                                interval_start=bar.at.isoformat(),
                                interval_end=bar.end_at.isoformat(),
                                source=dict(
                                    eod_manifest_sha256=bundle["raw_manifests"]["eod"],
                                    raw_price_date=day,
                                    snapshot=spec["snapshot"]["version"],
                                ),
                            )
                        )
            if not blockers and cutoff is not None:
                # Verified entry may be later than the research observation window.
                report["stock_model"] = simulate_stock(
                    available_at=cutoff,
                    bars=history.bars,
                    target1=rec.stock_target1,
                    target2=rec.stock_target2,
                    stop1=rec.stock_stop1,
                    stop2=rec.stock_stop2,
                    rules=rule,
                    horizon=as_of,
                )
                eligible = [b for b in history.bars if b.at > cutoff and b.end_at <= as_of]
                report["stock_model"]["modeled_entry_at"] = (
                    eligible[0].at.isoformat()
                    if eligible and report["stock_model"].get("modeled_entry") is not None
                    else None
                )
                report["stock_model"]["entry_source"] = (
                    dict(
                        eod_manifest_sha256=bundle["raw_manifests"]["eod"],
                        raw_price_date=eligible[0].at.date().isoformat(),
                        snapshot=spec["snapshot"]["version"],
                    )
                    if report["stock_model"]["modeled_entry_at"]
                    else None
                )
                if report["stock_model"]["status"] == "unknown":
                    blockers.append(report["stock_model"]["reason"])
                else:
                    report["quality"]["classification"] = (
                        "research_only"
                        if strict_reason or audit.get("research_assumption")
                        else "fully_evaluable_hypothetical_stock_model"
                        if report["stock_model"]["fully_evaluable"]
                        else "censored_or_ambiguous_stock_model"
                    )
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError) as exc:
            reason = "market_archive_integrity_or_schema_failed"
            blockers.append(reason)
            report["historical_market_data"].update(
                status="invalid_archive",
                issues=[reason],
                error_type=type(exc).__name__,
            )
    return finish()
