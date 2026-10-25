"""Read-only whole-archive orchestration and reproducible opportunity reports."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from scanner.opportunities.short_term import OpportunityPolicy, evaluate_candidate
from scanner.research import AssetIdentity


def _canonical_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _archive_identity(listing: dict) -> AssetIdentity:
    return AssetIdentity(
        asset_type="stock",
        name=listing["ticker"],
        ticker=listing["ticker"],
        cik=listing.get("cik"),
        isin=listing.get("isin"),
        exchange=listing.get("exchange"),
        mic=listing.get("mic"),
    )


def _identity_failure(listing: dict, reason: str) -> dict:
    return {
        "asset_id": listing["asset_id"],
        "ticker": listing.get("ticker"),
        "name": listing.get("ticker") or listing["asset_id"],
        "exchange": listing.get("exchange"),
        "mic": listing.get("mic"),
        "currency": listing.get("currency"),
        "status": "unavailable",
        "score": 0,
        "score_reasons": [],
        "selection_reasons": [],
        "failed_gates": [reason],
        "uncertainties": [],
        "features": None,
        "catalysts": [],
        "risk": None,
        "historical_availability_verified": False,
        "training_eligible": False,
        "probability_claimed": False,
        "requested_signal_date": None,
        "market_data_cutoff_at": None,
        "data_age_calendar_days": None,
    }


def run_dry_run(
    index,
    archive,
    *,
    as_of: datetime,
    signal_date: date,
    benchmark_asset_id: str | None = None,
    minimum_liquidity: Decimal = Decimal("1000000"),
    pilot_coverage: dict | None = None,
) -> dict:
    """Evaluate every archived listing without network, writes or execution claims."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not minimum_liquidity.is_finite() or minimum_liquidity <= 0:
        raise ValueError("minimum_liquidity must be finite and positive")
    as_of = as_of.astimezone(UTC)
    if as_of.date() < signal_date:
        raise ValueError("as_of precedes requested signal date")
    archive_sha256 = archive.logical_sha256()
    source_pilot = None
    if pilot_coverage is not None:
        if pilot_coverage.get("archive_sha256") != archive_sha256:
            raise ValueError("pilot coverage archive mismatch")
        if (
            pilot_coverage.get("coverage_kind") != "real_provider_archive"
            or pilot_coverage.get("real_provider_coverage_measured") is not True
        ):
            raise ValueError("pilot coverage is not measured real-provider data")
        rows = pilot_coverage.get("instruments") or []
        incomplete = [
            {
                "ticker": row.get("ticker"),
                "status": row.get("status"),
                "session_count": row.get("session_count", 0),
            }
            for row in rows
            if row.get("status") != "imported" or int(row.get("session_count", 0)) < 250
        ]
        source_pilot = {
            "status": pilot_coverage.get("status"),
            "selected_count": pilot_coverage.get("selected_count"),
            "successful_instruments": pilot_coverage.get("successful_instruments"),
            "requests_attempted": pilot_coverage.get("requests_attempted"),
            "cost_eur": str(pilot_coverage.get("cost_eur", "0")),
            "coverage_report_sha256": pilot_coverage.get("coverage_report_sha256"),
            "coverage_kind": pilot_coverage.get("coverage_kind"),
            "real_provider_coverage_measured": True,
            "failed_or_incomplete": sorted(incomplete, key=lambda row: row["ticker"] or ""),
        }
    evaluation_at = datetime.combine(signal_date, time.max, tzinfo=UTC)
    instruments = archive.list_instruments()
    benchmark_bars = None
    benchmark_status = "not_requested"
    if benchmark_asset_id:
        benchmark_status = "missing_archive_identity"
        benchmark_listing = next(
            (row for row in instruments if row["asset_id"] == benchmark_asset_id), None
        )
        if benchmark_listing is not None:
            benchmark_resolution = index.resolve_identity(
                _archive_identity(benchmark_listing), as_of=as_of
            )
            if (
                benchmark_resolution["status"] == "ok"
                and benchmark_resolution["asset_id"] == benchmark_asset_id
            ):
                candidate_benchmark = archive.prices(
                    benchmark_asset_id,
                    start=(signal_date - timedelta(days=500)).isoformat(),
                    end=signal_date.isoformat(),
                    as_of=as_of,
                    availability_mode="modeled",
                )["prices"]
                if len(candidate_benchmark) >= 21:
                    benchmark_bars = candidate_benchmark
                    benchmark_status = "available"
                else:
                    benchmark_status = "insufficient_history"
            else:
                benchmark_status = "identity_conflict"

    results = []
    matched = 0
    conflicts = 0
    for listing in instruments:
        supplied = _archive_identity(listing)
        resolution = index.resolve_identity(supplied, as_of=as_of)
        if resolution["status"] != "ok" or resolution["asset_id"] != listing["asset_id"]:
            conflicts += 1
            results.append(_identity_failure(listing, "identity_conflict"))
            continue
        matched += 1
        identity = AssetIdentity.model_validate(resolution["identity"])
        price_result = archive.prices(
            listing["asset_id"],
            start=(signal_date - timedelta(days=500)).isoformat(),
            end=signal_date.isoformat(),
            as_of=as_of,
            availability_mode="modeled",
        )
        prices = price_result["prices"]
        if prices:
            latest = max(prices, key=lambda row: row["session_date"])
            signal_at = datetime.fromisoformat(latest["modeled_available_at"])
        else:
            signal_at = datetime.combine(signal_date, time.max, tzinfo=UTC)
        evidence = index.opportunity_evidence(identity, as_of=signal_at)
        candidate = evaluate_candidate(
            identity,
            prices,
            as_of=evaluation_at,
            catalysts=evidence,
            benchmark_bars=benchmark_bars,
            policy=OpportunityPolicy(min_median_dollar_volume=minimum_liquidity),
        )
        results.append(
            candidate.model_dump(mode="json")
            | {
                "currency": listing.get("currency"),
                "requested_signal_date": signal_date.isoformat(),
                "market_data_cutoff_at": signal_at.isoformat() if prices else None,
                "data_age_calendar_days": (
                    signal_date - date.fromisoformat(latest["session_date"])
                ).days
                if prices
                else None,
            }
        )

    status_order = {"candidate_research": 0, "watch_only": 1, "unavailable": 2}
    results.sort(
        key=lambda row: (
            status_order[row["status"]],
            -row["score"],
            row["asset_id"],
        )
    )
    index_coverage = index.coverage(as_of)
    visible_assets = index_coverage["visible_assets"]
    coverage = {
        "archive_instruments": len(instruments),
        "research_index_visible_assets": visible_assets,
        "archive_coverage_of_visible_assets": (
            str(Decimal(matched) / Decimal(visible_assets)) if visible_assets else None
        ),
        "identity_matched": matched,
        "identity_conflicts": conflicts,
        "candidate_research": sum(row["status"] == "candidate_research" for row in results),
        "watch_only": sum(row["status"] == "watch_only" for row in results),
        "unavailable": sum(row["status"] == "unavailable" for row in results),
        "analyzed": sum(row.get("features") is not None for row in results),
        "gate_reason_counts": {
            reason: sum(reason in row["failed_gates"] for row in results)
            for reason in sorted({reason for row in results for reason in row["failed_gates"]})
        },
    }
    if benchmark_asset_id and benchmark_bars:
        eligible = [row for row in results if row.get("features") is not None]
        benchmark_matches = sum(
            row["features"].get("benchmark_status") == "available" for row in eligible
        )
        if eligible and benchmark_matches == len(eligible):
            benchmark_status = "available"
        elif benchmark_matches:
            benchmark_status = "partial_session_alignment"
        else:
            benchmark_status = "unavailable_for_candidate_sessions"
    top_candidates = [row for row in results if row["status"] == "candidate_research"][:10]
    return {
        "schema_version": "2.5.2",
        "mode": "modeled_research",
        "as_of": as_of.isoformat(),
        "signal_date": signal_date.isoformat(),
        "availability": "hypothetical_modeled_session_close",
        "historical_availability_verified": False,
        "training_eligible": False,
        "network_requests": 0,
        "cost_eur": "0",
        "archive_sha256": archive_sha256,
        "index_payload_sha256": index.manifest.payload_sha256,
        "benchmark_asset_id": benchmark_asset_id,
        "benchmark_status": benchmark_status,
        "source_pilot": source_pilot,
        "coverage": coverage,
        "top_candidates": top_candidates,
        "results": results,
    }


def write_report(report: dict, output_dir) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "opportunities.json"
    csv_path = output / "opportunities.csv"
    sha_path = output / "opportunities.sha256"
    json_payload = _canonical_bytes(report)
    json_path.write_bytes(json_payload)
    fields = (
        "rank",
        "asset_id",
        "ticker",
        "name",
        "exchange",
        "mic",
        "currency",
        "status",
        "score",
        "score_reasons",
        "selection_reasons",
        "failed_gates",
        "uncertainties",
        "signal_date",
        "requested_signal_date",
        "market_data_cutoff_at",
        "data_age_calendar_days",
        "reference_price",
        "gross_crv",
        "net_crv",
        "training_eligible",
        "features_json",
        "catalysts_json",
        "risk_json",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for rank, row in enumerate(report["results"], start=1):
            features = row.get("features") or {}
            risk = row.get("risk") or {}
            writer.writerow(
                {
                    "rank": rank,
                    "asset_id": row["asset_id"],
                    "ticker": row.get("ticker") or "",
                    "name": row["name"],
                    "exchange": row.get("exchange") or "",
                    "mic": row.get("mic") or "",
                    "currency": row.get("currency") or "",
                    "status": row["status"],
                    "score": row["score"],
                    "score_reasons": "|".join(row["score_reasons"]),
                    "selection_reasons": "|".join(row["selection_reasons"]),
                    "failed_gates": "|".join(row["failed_gates"]),
                    "uncertainties": "|".join(row["uncertainties"]),
                    "signal_date": features.get("signal_date", ""),
                    "requested_signal_date": row.get("requested_signal_date") or "",
                    "market_data_cutoff_at": row.get("market_data_cutoff_at") or "",
                    "data_age_calendar_days": row.get("data_age_calendar_days")
                    if row.get("data_age_calendar_days") is not None
                    else "",
                    "reference_price": risk.get("reference_price", ""),
                    "gross_crv": risk.get("gross_crv", ""),
                    "net_crv": risk.get("net_crv", ""),
                    "training_eligible": str(row["training_eligible"]).lower(),
                    "features_json": json.dumps(
                        row.get("features"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "catalysts_json": json.dumps(
                        row.get("catalysts"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "risk_json": json.dumps(
                        row.get("risk"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                }
            )
    digest = hashlib.sha256(json_payload).hexdigest()
    csv_digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    sha_path.write_text(
        f"{digest}  {json_path.name}\n{csv_digest}  {csv_path.name}\n", encoding="ascii"
    )
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "sha256_file": str(sha_path),
        "sha256": digest,
        "csv_sha256": csv_digest,
    }
