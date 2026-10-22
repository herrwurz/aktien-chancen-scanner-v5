"""Read-only V1.6 evaluation, reusing every V1.5 identity and source gate."""

import csv
import json
import os
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .backtest import simulate_stock
from .backtest_provider import _at
from .backtest_report import document_rules
from .eodhd import canonical, sha
from .eodhd_adapter import EodhdStockProvider
from .historical_pipeline import build_pipeline_report, write_audit
from .models import Document, HistoricalRecommendation


def build_v16_report(session, *, synthetic=False, archive_audit=None, **kwargs):
    report = build_pipeline_report(session, **kwargs)
    report.pop("report_sha256", None)
    report["version"] = "hebel-backtest-pipeline-v1.6"
    report["measurement_scope"] = (
        "synthetic"
        if synthetic
        else "supplied_archive_and_market_inputs"
        if archive_audit and kwargs.get("bundles")
        else "local_inputs_only; external_Hetzner_coverage_unmeasured"
    )
    report["openfigi_archive_audit"] = archive_audit
    if archive_audit and archive_audit["errors"]:
        report["warnings"].append("openfigi_archive_integrity_failed")
    provider = (
        EodhdStockProvider(kwargs["market_root"], kwargs["raw_cache"], kwargs["bundles"])
        if kwargs.get("market_root") and kwargs.get("raw_cache") and kwargs.get("bundles")
        else None
    )
    with session.no_autoflush:
        originals = {
            f"{doc.sha256}:{rec.ordinal}": (doc, rec)
            for doc, rec in session.execute(
                select(Document, HistoricalRecommendation).join(
                    HistoricalRecommendation,
                    HistoricalRecommendation.document_sha == Document.sha256,
                )
            )
        }
        for row in report["results"]:
            doc, rec = originals[row["recommendation_key"]]
            rule, audit, issue = document_rules(
                doc,
                rec,
                (kwargs.get("rules") or {}).get(row["recommendation_key"]),
                kwargs["run_at"],
            )
            extra = []
            if issue or not rule or rule.version != "1.6":
                extra.append(issue or "complete_reviewed_v16_rules_required")
            if archive_audit and archive_audit["errors"]:
                extra.append("openfigi_archive_integrity_failed")
            row["v16_rules"] = audit
            row["blockers"] = sorted(set(row["blockers"] + extra))
            for mode, gate in row["mode_audit"].items():
                blockers = list(extra)
                if mode == "verified" and audit and audit.get("research_assumption"):
                    blockers.append("unverified_time_unit_interpretation")
                gate["blockers"] = sorted(set(gate["blockers"] + blockers))
                gate["ready"] = gate["ready"] and not blockers
            mode = kwargs.get("analysis_mode", "research")
            gate = row["mode_audit"][mode]
            row["backtest"] = dict(
                status="unknown",
                reason="prerequisites_missing",
                blockers=gate["blockers"],
                fully_evaluable=False,
                modeled_return_pct=None,
                realized_return_pct=None,
                training_eligible=False,
                events=[],
                metrics={},
            )
            if not gate["ready"] or provider is None:
                continue
            cutoff = _at(gate["entry_policy"]["entry_cutoff_exclusive"])
            history = provider.load(
                row["identity"]["selected"],
                instrument=dict(
                    wkn=rec.stock_wkn,
                    isin=rec.stock_isin,
                    currency=rec.stock_currency,
                    levels_as_of=datetime.combine(
                        doc.publication_date, time.min, ZoneInfo("Europe/Berlin")
                    ),
                ),
                available_at=cutoff,
                as_of=kwargs["as_of"],
            )
            if history.issues:
                row["backtest"]["blockers"] = history.issues
                continue
            row["backtest"] = simulate_stock(
                available_at=cutoff,
                bars=history.bars,
                target1=rec.stock_target1,
                target2=rec.stock_target2,
                stop1=rec.stock_stop1,
                stop2=rec.stock_stop2,
                horizon=kwargs["as_of"],
                rules=rule,
            )
    outcomes = [r["backtest"] for r in report["results"]]
    count = len(outcomes)
    report["evaluation_summary"] = dict(
        recommendations=count,
        fully_evaluable=sum(o["fully_evaluable"] for o in outcomes),
        fully_evaluable_fraction=(
            sum(o["fully_evaluable"] for o in outcomes) / count if count else None
        ),
        censored_open=sum(o["status"] == "open" for o in outcomes),
        ambiguous=sum(o["status"] == "ambiguous" for o in outcomes),
        missing_prerequisites=sum(o["status"] == "unknown" for o in outcomes),
        confirmed_historical_successes=None,
        warrant_returns=None,
        hypothetical=True,
        training_eligible=False,
    )
    for mode in ("research", "verified"):
        report["pipeline_summary"][mode + "_backtest_ready"] = sum(
            r["mode_audit"][mode]["ready"] for r in report["results"]
        )
    report["remaining_data_gaps"] = sorted(
        {
            b
            for r in report["results"]
            for gate in r["mode_audit"].values()
            for b in gate["blockers"]
        }
    )
    report["report_sha256"] = sha(canonical(report))
    return report


def write_verified_audit(prefix, report):
    """Exclusive artifacts, plus hashes of their actual bytes (prefix independent)."""
    sidecar = Path(str(prefix) + ".sha256.json")
    # Reserve before touching any other output; never overwrite an existing run.
    sidecar.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    created = []
    try:
        created = write_audit(prefix, report)
        hashes = {str(p)[len(str(prefix)) :]: sha(p.read_bytes()) for p in created}
        sidecar.write_bytes(canonical(dict(version="1.6", files=hashes)))
        return [*created, sidecar]
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise


def verify_audit(prefix):
    index = json.loads(Path(str(prefix) + ".sha256.json").read_bytes())
    expected = {".json", ".csv", ".identities.json", ".identities.csv"}
    if set(index["files"]) != expected:
        raise ValueError("unexpected artifact set")
    for suffix, digest in index["files"].items():
        if sha(Path(str(prefix) + suffix).read_bytes()) != digest:
            raise ValueError("artifact integrity error")
    report = json.loads(Path(str(prefix) + ".json").read_bytes())
    digest = report.pop("report_sha256")
    if sha(canonical(report)) != digest:
        raise ValueError("report integrity error")
    for suffix, rows in (
        (".csv", report["results"]),
        (".identities.csv", report["identity_audit"]["identities"]),
    ):
        with Path(str(prefix) + suffix).open() as stream:
            if [json.loads(r["record_json"]) for r in csv.DictReader(stream)] != rows:
                raise ValueError("JSON/CSV mismatch")
    return True
