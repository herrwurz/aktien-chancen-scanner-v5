"""Exclusive, reproducible pilot JSON/CSV/Markdown plus byte-level SHA-256 index."""

import csv
import io
import json
import os
from pathlib import Path

from .eodhd import canonical, sha


def _rows(report):
    yield "original_recommendation", report["original_recommendation"]
    yield "historical_market_data", report["historical_market_data"]
    for event in report["price_events"]:
        yield "stock_price_observation", event
    yield "stock_model_summary", report["stock_model"]
    for event in report["stock_model"]["events"]:
        yield "hypothetical_stock_execution", event
    yield "derivative_observations", report["derivative_observations"]
    yield "quality", report["quality"]


def summary(report):
    values = report["original_recommendation"].get("values", {})
    model = report["stock_model"]
    quality = report["quality"]
    lines = [
        "# JNJ-Pilot V1.7",
        "",
        f"Datenklasse: {report['data_classification']}",
        f"Original: {report['recommendation_key']}",
        f"Fenster: {report['window']['start_date']} bis {report['window']['end_date']} "
        f"({report['window']['scope']})",
        "",
        "| Originalfeld | Wert |",
        "|---|---|",
    ]
    for field, value in sorted(values.items()):
        clean = str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {field} | {clean} |")
    lines.extend(
        [
            "",
            f"Identität: {report['identity']['status']}",
            f"Marktdaten: {report['historical_market_data']['status']}; "
            f"vollständige Kerzen: {report['historical_market_data']['complete_bars']}",
            f"Potenzielle Aktienkursberührungen: {len(report['price_events'])}",
            f"Qualitätsklasse: {quality['classification']}",
            f"Hypothetisches Aktienmodell: {model['status']}",
            f"Modelleinstieg: {model.get('modeled_entry_at')} zu {model.get('modeled_entry')} USD",
            f"Modellierter beobachteter Drawdown (%): "
            f"{model.get('metrics', {}).get('observed_equity_max_drawdown_pct')}",
            f"Modellierte Brutto-Preisrendite (%): {model.get('modeled_return_pct')}",
            f"Konservative Untergrenze (%): {model.get('conservative_return_pct')}",
            f"Optionsscheinrendite: {report['derivative_observations']['return_pct']} "
            "(keine historischen Bid-/Ask-Daten)",
            "",
            "Blocker:",
            *["- " + b for b in quality["blockers"]],
            "",
            "Unsicherheiten:",
            *["- " + b for b in quality["uncertainties"]],
            "",
            "Kursberührungen sind keine Ausführungsbelege. Der Untersuchungszeitraum ist keine "
            "Haltedauer- oder Erfolgsregel. training_eligible=false.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(prefix, report):
    prefix = Path(prefix)
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["record_type", "document_sha", "ordinal", "record_json"])
    for kind, payload in _rows(report):
        writer.writerow(
            [
                kind,
                report["original_recommendation"]["document_sha"],
                1,
                json.dumps(payload, sort_keys=True, ensure_ascii=False),
            ]
        )
    parts = {
        ".json": canonical(report),
        ".csv": out.getvalue().encode(),
        ".md": summary(report).encode(),
    }
    parts[".sha256.json"] = canonical(
        dict(version="1.7", files={k: sha(v) for k, v in parts.items()})
    )
    prefix.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    try:
        # Reserve all outputs before writing; don't leave partial new runs on conflicts.
        streams = []
        try:
            for suffix in parts:
                path = Path(str(prefix) + suffix)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created.append(path)
                streams.append(os.fdopen(fd, "wb"))
            for stream, payload in zip(streams, parts.values(), strict=True):
                stream.write(payload)
        finally:
            for stream in streams:
                stream.close()
        return created
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def verify_report(prefix):
    index = json.loads(Path(str(prefix) + ".sha256.json").read_bytes())
    if set(index["files"]) != {".json", ".csv", ".md"}:
        raise ValueError("unexpected pilot artifact set")
    for suffix, digest in index["files"].items():
        if sha(Path(str(prefix) + suffix).read_bytes()) != digest:
            raise ValueError("pilot artifact integrity error")
    report = json.loads(Path(str(prefix) + ".json").read_bytes())
    original_hash = report.pop("report_sha256")
    if sha(canonical(report)) != original_hash:
        raise ValueError("pilot report integrity error")
    with Path(str(prefix) + ".csv").open() as stream:
        records = list(csv.DictReader(stream))
    expected = [
        (kind, report["original_recommendation"]["document_sha"], "1", payload)
        for kind, payload in _rows(report)
    ]
    actual = [
        (r["record_type"], r["document_sha"], r["ordinal"], json.loads(r["record_json"]))
        for r in records
    ]
    if actual != expected or Path(str(prefix) + ".md").read_text() != summary(report):
        raise ValueError("pilot JSON/CSV/Markdown mismatch")
    return True
