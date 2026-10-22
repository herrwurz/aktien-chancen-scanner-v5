"""Offline V1.4 preparation: proposals only, no persistence or historical labels."""

import hashlib
import json
from collections import Counter

from sqlalchemy import select

from scanner.hebeltrader.identity_assistant import suggest_identity, validate_source_cache
from scanner.hebeltrader.models import Document, HistoricalRecommendation
from scanner.hebeltrader.preparation_quality import assess_quality, group_quality
from scanner.hebeltrader.rule_assistant import suggest_rules


def build_preparation(
    session, *, run_at, source_records=(), identity_cache=None, expected_count=118
):
    if run_at.utcoffset() is None:
        raise ValueError("Timezone-aware replay clock required")
    sources = validate_source_cache(list(source_records), identity_cache)
    results, findings, instruments = [], [], {}
    with session.no_autoflush:
        pairs = session.execute(
            select(Document, HistoricalRecommendation)
            .join(
                HistoricalRecommendation, HistoricalRecommendation.document_sha == Document.sha256
            )
            .order_by(Document.sha256, HistoricalRecommendation.ordinal)
        )
        for doc, rec in pairs:
            key = f"{doc.sha256}:{rec.ordinal}"
            rules = suggest_rules(doc, rec, run_at=run_at)
            defects = assess_quality(doc, rec)
            findings.extend(defects)
            if rec.stock_wkn:
                instrument = instruments.setdefault(
                    rec.stock_wkn,
                    dict(wkn=rec.stock_wkn, recommendation_keys=[], publication_dates=[]),
                )
                instrument["recommendation_keys"].append(key)
                if doc.publication_date:
                    instrument["publication_dates"].append(doc.publication_date.isoformat())
            results.append(
                dict(
                    recommendation_key=key,
                    document_sha=doc.sha256,
                    ordinal=rec.ordinal,
                    publication_date=str(doc.publication_date) if doc.publication_date else None,
                    stock_wkn=rec.stock_wkn,
                    stock_isin=rec.stock_isin,
                    original_sha_valid="original_sha_mismatch" not in rules["review_hints"],
                    rules=rules,
                    quality_findings=defects,
                    requires_manual_review=True,
                    hypothetical=True,
                    training_eligible=False,
                )
            )
    identities = []
    for instrument in instruments.values():
        instrument["publication_dates"] = sorted(set(instrument["publication_dates"]))
        identities.append(
            dict(
                instrument,
                **{
                    k: v
                    for k, v in suggest_identity(instrument, sources, run_at=run_at).items()
                    if k != "wkn"
                },
            )
        )
    quality = group_quality(findings)
    summary = dict(
        recommendations=len(results),
        documents=len({r["document_sha"] for r in results}),
        expected_count=expected_count,
        count_matches=len(results) == expected_count,
        original_sha_valid=sum(r["original_sha_valid"] for r in results),
        recommendations_with_rule_candidates=sum(bool(r["rules"]["candidates"]) for r in results),
        recommendations_with_action_drafts=sum(
            any(
                k in r["rules"]["rules_json_candidate"]
                for k in ("partial_fraction", "after_target1", "exit_after")
            )
            for r in results
        ),
        rule_candidate_kinds=dict(
            sorted(Counter(c["kind"] for r in results for c in r["rules"]["candidates"]).items())
        ),
        stock_wkn_occurrences=sum(bool(r["stock_wkn"]) for r in results),
        unique_stock_wkn=len(identities),
        identities_with_candidates=sum(bool(i["candidates"]) for i in identities),
        verified_identities=0,
        automatically_approved_rules=0,
        manual_review_recommendations=len(results),
        quality_affected_documents=quality["affected_documents"],
        quality=quality["summary"],
        backtest_readiness="not_assessed",
    )
    payload = dict(
        version="1.4",
        run_at=run_at.isoformat(),
        summary=summary,
        results=results,
        identities=identities,
        quality=quality,
        rules_draft={r["recommendation_key"]: r["rules"]["rules_json_candidate"] for r in results},
        identity_input={"instruments": list(instruments.values())},
        source_records=sources,
    )
    canonical = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    payload["input_and_result_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return payload
