"""V1.5 read-only inventory; imported data, verified identity and readiness are separate."""

import csv
import json
import os
from pathlib import Path

from sqlalchemy import select

from .backtest_provider import _at
from .coverage import build_coverage
from .eodhd import canonical, sha
from .eodhd_adapter import EodhdStockProvider
from .historical_identity import ReviewedIdentityProvider, audit_identities
from .market_snapshot import _credentials
from .models import Document, HistoricalRecommendation


def build_pipeline_report(
    session,
    *,
    run_at,
    as_of,
    records=(),
    cache_dir=None,
    mapping=None,
    rules=None,
    bundles=(),
    market_root=None,
    raw_cache=None,
    expected_count=118,
    analysis_mode="research",
    reported_openfigi_hits=None,
):
    _credentials(mapping or {})
    _credentials(rules or {})
    _credentials(list(bundles))
    inputs = []
    with session.no_autoflush:
        for doc, rec in session.execute(
            select(Document, HistoricalRecommendation)
            .join(
                HistoricalRecommendation, HistoricalRecommendation.document_sha == Document.sha256
            )
            .order_by(Document.sha256, HistoricalRecommendation.ordinal)
        ):
            inputs.append(
                dict(
                    wkn=rec.stock_wkn,
                    derivative_wkn=rec.derivative_wkn,
                    document_sha=doc.sha256,
                    ordinal=rec.ordinal,
                    stock_name=rec.stock_name,
                    publication_date=str(doc.publication_date) if doc.publication_date else None,
                    stock_wkn_evidence=rec.evidence.get("stock_wkn", []),
                    derivative_wkn_evidence=rec.evidence.get("derivative_wkn", []),
                )
            )
    identities = audit_identities(inputs, list(records), run_at=run_at, cache_dir=cache_dir)
    blocked = {
        r["wkn"]
        for r in identities["identities"]
        if r["classification_status"].startswith("quarantined")
    }
    candidates = {
        k: v.copy() if isinstance(v, list) else [dict(v)] for k, v in (mapping or {}).items()
    }
    for bundle in bundles:
        spec = bundle["spec"]
        key = spec.get("wkn") or spec.get("isin")
        candidates.setdefault(key, []).append(spec)
    resolver = ReviewedIdentityProvider(
        candidates, list(records), run_at=run_at, cache_dir=cache_dir, blocked_wkn=blocked
    )
    market = (
        EodhdStockProvider(market_root, raw_cache, list(bundles))
        if bundles and market_root and raw_cache
        else None
    )

    def inventory(mode):
        return build_coverage(
            session,
            candidates,
            rules or {},
            as_of=as_of,
            run_at=run_at,
            expected_count=expected_count,
            analysis_mode=mode,
            identity_provider=resolver,
            market_provider=market,
        )

    mode_reports = {mode: inventory(mode) for mode in ("research", "verified")}
    report = mode_reports[analysis_mode]
    by_wkn = {r["wkn"]: r for r in identities["identities"]}
    for row in report["results"]:
        identity = by_wkn.get(row["values"]["stock_wkn"])
        row["public_identity_candidates"] = identity["candidates"] if identity else []
        row["classification_status"] = (
            identity["classification_status"] if identity else "missing_stock_identifier"
        )
        row["scientific_scope"] = (
            "hypothetical_stock_price_model; no executed transaction or warrant pricing"
        )
        row["warrant_backtest_missing"] = [
            "historical_derivative_bid_ask",
            "historical_product_terms",
            "executable_quotes_and_liquidity",
            "costs_and_execution_model",
        ]
    series = []
    for bundle in bundles:
        spec = bundle["spec"]
        if market is None:
            series.append(dict(symbol=spec.get("symbol"), bars=0, issues=["market_roots_missing"]))
            continue
        history = market.load(
            spec,
            instrument=dict(
                wkn=spec.get("wkn"), isin=spec.get("isin"), currency=spec.get("currency")
            ),
            available_at=_at(spec["coverage_start"]),
            as_of=min(as_of, _at(spec["coverage_end"])),
        )
        series.append(
            dict(
                symbol=spec["symbol"],
                venue=spec["venue"],
                snapshot=spec["snapshot"]["version"],
                bars=len(history.bars),
                issues=history.issues,
            )
        )
    required = (
        "publication_evidenced",
        "instrument_identity_verified",
        "rules_documented",
        "market_history_sufficient",
        "modeled_entry_executable",
    )

    def ready(row, strict=False):
        stages = (*required, *(["verified_availability"] if strict else []))
        return all(row["stages"][key]["status"] == "complete" for key in stages)

    by_mode = {
        mode: {r["recommendation_key"]: r for r in item["results"]}
        for mode, item in mode_reports.items()
    }
    for row in report["results"]:
        row["mode_audit"] = {
            mode: dict(
                ready=ready(rows[row["recommendation_key"]], mode == "verified"),
                entry_policy=rows[row["recommendation_key"]]["entry_policy"],
                modeled_entry_at=rows[row["recommendation_key"]]["modeled_entry_at"],
                blockers=rows[row["recommendation_key"]]["blockers"],
            )
            for mode, rows in by_mode.items()
        }
    report["version"] = "hebel-historical-pipeline-v1.5"
    report["identity_audit"] = identities
    report["series_audit"] = series
    report["external_reported_openfigi"] = dict(
        wkn_with_candidates=reported_openfigi_hits,
        provenance="user-reported Hetzner audit; external files not implied to be locally read",
        locally_observed_wkn_with_candidates=identities["openfigi_wkn_with_candidates"],
    )
    report["pipeline_summary"] = dict(
        unique_wkn=identities["unique_wkn"],
        openfigi_input_status=(
            "not_supplied"
            if not identities["queried_openfigi_wkn"]
            else "complete"
            if identities["queried_openfigi_wkn"] == identities["unique_wkn"]
            else "partial_or_invalid"
        ),
        openfigi_candidates_observed=identities["openfigi_wkn_with_candidates"],
        ambiguous_venue_wkn=identities["multiple_venue_wkn"],
        classification_conflicts=identities["classification_conflicts"],
        historical_identities_verified=len(
            {
                tuple(
                    r["identity"]["selected"].get(k)
                    for k in (
                        "wkn",
                        "isin",
                        "symbol",
                        "venue",
                        "identity_valid_from",
                        "identity_valid_until",
                    )
                )
                for r in report["results"]
                if r["identity"]["selected"] is not None
            }
        ),
        recommendations_with_verified_identity=sum(
            r["stages"]["instrument_identity_verified"]["status"] == "complete"
            for r in report["results"]
        ),
        imported_series=sum(s["bars"] > 0 for s in series),
        imported_series_with_quality_issues=sum(bool(s["issues"]) for s in series),
        recommendations_with_sufficient_history=sum(
            r["stages"]["market_history_sufficient"]["status"] == "complete"
            for r in report["results"]
        ),
        research_backtest_ready=sum(ready(r) for r in mode_reports["research"]["results"]),
        verified_backtest_ready=sum(ready(r, True) for r in mode_reports["verified"]["results"]),
        warrant_backtest_ready=0,
        network_access_during_audit=False,
        missing_stock_identifiers=sum(not i["wkn"] for i in inputs),
        maximum_external_monthly_budget_eur=100,
    )
    report["report_sha256"] = sha(canonical(report))
    return report


def write_audit(prefix, report):
    prefix = Path(prefix)
    parts = {
        ".json": report,
        ".csv": report["results"],
        ".identities.json": report["identity_audit"],
        ".identities.csv": report["identity_audit"]["identities"],
    }
    prefix.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    streams, created = {}, []
    try:
        for suffix in parts:
            path = Path(str(prefix) + suffix)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            streams[suffix] = os.fdopen(fd, "w", encoding="utf-8", newline="")
        for suffix, payload in parts.items():
            stream = streams[suffix]
            if suffix.endswith(".csv"):
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(["document_sha_or_wkn", "ordinal", "record_json"])
                for row in payload:
                    writer.writerow(
                        [
                            row.get("document_sha", row.get("wkn")),
                            row.get("ordinal"),
                            json.dumps(row, sort_keys=True, ensure_ascii=False, default=str),
                        ]
                    )
            else:
                json.dump(
                    payload, stream, sort_keys=True, ensure_ascii=False, indent=2, default=str
                )
                stream.write("\n")
        return created
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        for stream in streams.values():
            stream.close()
