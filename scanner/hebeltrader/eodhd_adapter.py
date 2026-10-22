"""Offline conversion: raw prices, independently supplied sessions, no guessed fills."""

import csv
import io
import re
import shutil
import tempfile
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .backtest import Bar
from .backtest_provider import MarketHistory, _at
from .eodhd import canonical, read_record, sha
from .market_snapshot import SnapshotStockProvider, snapshot_dataset


def _csv(rows, columns):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def prepare_snapshot(cache_root, output_root, *, records, spec, calendar_path, run_at):
    if run_at.utcoffset() is None or not re.fullmatch(r"[A-Z0-9]{4}", spec["venue"]):
        raise ValueError(
            "aware clock and explicit MIC required; composite exchange codes are not MICs"
        )
    if set(records) != {"eod", "splits", "div"}:
        raise ValueError("prices, splits and dividends snapshots all required")
    zone = ZoneInfo(spec["timezone"])
    first, last = _at(spec["coverage_start"]), _at(spec["coverage_end"])
    if first > last or last > run_at:
        raise ValueError("invalid or future coverage")
    raw_records = {k: read_record(cache_root, v) for k, v in records.items()}
    for endpoint, record in raw_records.items():
        req = record["request"]
        if req["endpoint"] != endpoint or req["symbol"] != spec["symbol"]:
            raise ValueError("raw source instrument or endpoint mismatch")
        if (
            not req.get("start")
            or not req.get("end")
            or req["start"] > first.astimezone(zone).date().isoformat()
            or req["end"] < last.astimezone(zone).date().isoformat()
        ):
            raise ValueError("price/action requests do not cover declared historical window")
        if not last <= _at(record["retrieved_at"]) <= run_at:
            raise ValueError("retrieval outside audit window")
        if not isinstance(record["payload"], list):
            raise ValueError("expected series arrays")
    calendar_raw = Path(calendar_path).read_bytes()
    calendar = list(csv.DictReader(io.StringIO(calendar_raw.decode("utf-8-sig"))))
    sessions = {}
    previous_close = None
    for row in calendar:
        opened, closed = _at(row["timestamp"]), _at(row["end_timestamp"])
        if any(t.utcoffset() != t.astimezone(zone).utcoffset() for t in (opened, closed)):
            raise ValueError("calendar offset does not match venue timezone")
        day = opened.astimezone(zone).date().isoformat()
        if day in sessions or closed <= opened or previous_close and opened < previous_close:
            raise ValueError("duplicate, overlapping or unordered sessions")
        sessions[day] = (opened, closed)
        previous_close = closed
    rows, seen = [], set()
    for row in raw_records["eod"]["payload"]:
        day = row["date"]
        if day not in sessions or day in seen:
            raise ValueError("duplicate price date or missing independently sourced session")
        opened, closed = sessions[day]
        if opened < first or closed > last:
            raise ValueError("price outside declared historical window")
        req = raw_records["eod"]["request"]
        if req["start"] and day < req["start"] or req["end"] and day > req["end"]:
            raise ValueError("price outside requested date window")
        # adjusted_close is deliberately never used for historical target comparisons.
        bar = Bar(
            at=opened,
            end_at=closed,
            **{k: Decimal(str(row[k])) for k in ("open", "high", "low", "close", "volume")},
        )
        rows.append(
            dict(
                timestamp=bar.at.isoformat(),
                end_timestamp=bar.end_at.isoformat(),
                **{k: str(getattr(bar, k)) for k in ("open", "high", "low", "close", "volume")},
            )
        )
        seen.add(day)
    if not rows:
        raise ValueError("empty price series")
    rows.sort(key=lambda r: r["timestamp"])
    actions = []
    for endpoint, kind in (("splits", "split"), ("div", "dividend")):
        for row in raw_records[endpoint]["payload"]:
            effective = datetime.combine(datetime.fromisoformat(row["date"]).date(), time.min, zone)
            if not first <= effective <= last:
                raise ValueError("corporate action outside coverage")
            if kind == "split" and not re.fullmatch(
                r"\d+(?:\.\d+)?/\d+(?:\.\d+)?", str(row.get("split", ""))
            ):
                raise ValueError("invalid split record")
            if kind == "dividend":
                amount = Decimal(str(row["value"]))
                if not amount.is_finite() or amount < 0:
                    raise ValueError("invalid dividend")
            actions.append(dict(timestamp=effective.isoformat(), type=kind))
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix=".eodhd-", dir=root))
    try:
        (temporary / "bars.csv").write_text(
            _csv(rows, ("timestamp", "end_timestamp", "open", "high", "low", "close", "volume"))
        )
        (temporary / "calendar.csv").write_bytes(calendar_raw)
        (temporary / "actions.csv").write_text(
            _csv(sorted(actions, key=lambda a: (a["timestamp"], a["type"])), ("timestamp", "type"))
        )
        manifest = dict(
            spec,
            adjustment="raw",
            source_reference=raw_records["eod"]["source_reference"],
            license=raw_records["eod"]["license"],
            retrieved_at=max((r["retrieved_at"] for r in raw_records.values()), key=_at),
            corporate_actions_reference=(
                "EODHD splits/dividends; effective dates only; reconciliation required"
            ),
            file=str((temporary / "bars.csv").relative_to(root)),
            calendar_file=str((temporary / "calendar.csv").relative_to(root)),
            corporate_actions_file=str((temporary / "actions.csv").relative_to(root)),
        )
        frozen = snapshot_dataset(root, root / "snapshots", manifest)
    finally:
        shutil.rmtree(temporary)
    bundle = dict(
        spec=frozen,
        raw_manifests=records,
        audit=dict(
            adapter_version="1.5",
            instrument="stock",
            venue=spec["venue"],
            volume_adjustment="split_adjusted_vendor",
            market_data_vintage="retrieval_snapshot; not proof of original historical availability",
            prices="unadjusted_ohlc",
            price_scope="vendor_eod; not evidence of executable MIC-specific quotes",
            calendar_source="independently_supplied_sessions",
            calendar_sha256=sha(calendar_raw),
            calendar_reference=spec["calendar_reference"],
            corporate_actions=len(actions),
            actions_reconciled=False,
            derivative_bid_ask_available=False,
            execution_claim=False,
            training_eligible=False,
        ),
    )
    return dict(bundle, bundle_sha256=sha(canonical(bundle)))


class EodhdStockProvider:
    """Validate original response integrity again before existing snapshot validation."""

    def __init__(self, root, cache_root, bundles):
        self.root, self.cache_root = Path(root), Path(cache_root)
        self.bundles = bundles

    def load(self, spec, **kwargs):
        try:
            matches = [
                b
                for b in self.bundles
                if b["spec"]["snapshot"]["version"] == spec["snapshot"]["version"]
            ]
            if len(matches) != 1:
                raise ValueError("ambiguous or missing vendor provenance")
            bundle = matches[0]
            if (
                sha(canonical({k: v for k, v in bundle.items() if k != "bundle_sha256"}))
                != bundle["bundle_sha256"]
            ):
                raise ValueError("bundle integrity error")
            for endpoint, digest in bundle["raw_manifests"].items():
                record = read_record(self.cache_root, digest)
                if (
                    record["request"]["endpoint"] != endpoint
                    or record["request"]["symbol"] != spec["symbol"]
                ):
                    raise ValueError("raw source mismatch")
            result = SnapshotStockProvider(self.root).load(spec, **kwargs)
            result.source["vendor_provenance"] = dict(
                raw_manifests=bundle["raw_manifests"], **bundle["audit"]
            )
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return MarketHistory([], {}, ["vendor_snapshot_integrity_error"])
