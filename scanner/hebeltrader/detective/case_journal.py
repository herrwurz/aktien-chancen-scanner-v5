"""Local append-only case lifecycle. Never supplied to the ranking engine."""

import fcntl
import hashlib
import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_frozen(path):
    envelope = json.loads(Path(path).read_text())
    if envelope.get("format") != "hebeltrader-frozen-analysis-v1" or digest(
        envelope.get("report")
    ) != envelope.get("sha256"):
        raise ValueError("frozen ranking integrity mismatch")
    return envelope


def input_keys(payload):
    text = unicodedata.normalize("NFKC", payload.get("teaser_text", ""))
    text = " ".join(text.casefold().split())
    content = (
        digest(
            {
                "text": text,
                "screenshot": payload.get("screenshot_base64"),
                "pdf": payload.get("pdf_base64"),
            }
        )
        if text or payload.get("screenshot_base64") or payload.get("pdf_base64")
        else None
    )
    url = payload.get("teaser_url") or payload.get("original_source_url")
    source = None
    if url:
        p = urlsplit(str(url))
        query = urlencode(
            sorted((k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_"))
        )
        url = urlunsplit((p.scheme, p.netloc.lower(), p.path, query, ""))
        edition = payload.get("issue") or payload.get("publication_at")
        source = digest({"url": url, "edition": edition, "content": None if edition else content})
    return content, source


class CaseJournal:
    def __init__(self, root, *, clock=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "cases.jsonl"
        self.clock = clock or (lambda: datetime.now(UTC))

    def events(self):
        if not self.path.exists():
            return []
        events, previous = [], "0" * 64
        for index, line in enumerate(self.path.read_text().splitlines(), 1):
            try:
                row = json.loads(line)
                checksum = row.pop("sha256")
                if (
                    row["seq"] != index
                    or row["previous_sha256"] != previous
                    or digest(row) != checksum
                ):
                    raise ValueError("hash mismatch")
                row["sha256"] = checksum
                events.append(row)
                previous = checksum
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("case journal integrity error") from exc
        return events

    def verify(self):
        rows = self.events()
        return {
            "valid": True,
            "events": len(rows),
            "head_sha256": rows[-1]["sha256"] if rows else "0" * 64,
        }

    def _append(self, case_id, kind, payload):
        rows = self.events()
        row = {
            "seq": len(rows) + 1,
            "case_id": case_id,
            "kind": kind,
            "recorded_at": self.clock().isoformat(),
            "previous_sha256": rows[-1]["sha256"] if rows else "0" * 64,
            "payload": payload,
        }
        row["sha256"] = digest(row)
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "ab") as handle:
                handle.write(canonical(row) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            raise
        return row

    def _lock(self):
        handle = (self.root / "cases.lock").open("a")
        fcntl.flock(handle, fcntl.LOCK_EX)
        return handle

    def intake(self, payload):
        # No history/solution fields are accepted as original input.
        if any(k in payload for k in ("resolution", "solution", "call_wkn", "correct_asset_id")):
            raise ValueError("solutions belong in post-freeze resolution")
        content, source = input_keys(payload)
        if not content and not source:
            raise ValueError("case original required")
        with self._lock():
            rows = self.events()
            for row in rows:
                if row["kind"] not in ("intake", "input_revision"):
                    continue
                p = row["payload"]
                known_content, known_source = input_keys(p["input"])
                if (content and content == known_content) or (source and source == known_source):
                    # Keep changed original as a new event, never overwrite the first.
                    if not any(
                        event["case_id"] == row["case_id"]
                        and event["kind"] in ("intake", "input_revision")
                        and event["payload"]["input_sha256"] == digest(payload)
                        for event in rows
                    ):
                        self._append(
                            row["case_id"],
                            "input_revision",
                            {"input": payload, "input_sha256": digest(payload)},
                        )
                    return row["case_id"]
            case_id = "TI-" + (source or content)[:20]
            self._append(
                case_id,
                "intake",
                {
                    "input": payload,
                    "input_sha256": digest(payload),
                    "content_key": content,
                    "source_key": source,
                },
            )
            return case_id

    def case(self, case_id):
        rows = [r for r in self.events() if r["case_id"] == case_id]
        if not rows or rows[0]["kind"] != "intake":
            raise ValueError("unknown case")
        state = {
            "case_id": case_id,
            "status": "neu",
            "input": rows[0]["payload"]["input"],
            "input_sha256": rows[0]["payload"]["input_sha256"],
            "first_prediction": None,
            "latest_prediction": None,
            "resolution": None,
            "analyses": 0,
            "opened_at": rows[0]["recorded_at"],
            "first_frozen_at": None,
        }
        for row in rows:
            kind, p = row["kind"], row["payload"]
            if kind == "begin" and state["resolution"] is None:
                state["status"] = "in_analyse"
            if kind == "analysis":
                report = p["frozen"]["report"]
                state["first_frozen_at"] = state["first_frozen_at"] or p["frozen"]["frozen_at"]
                state["first_prediction"] = state["first_prediction"] or report
                state["latest_prediction"] = report
                state["analyses"] += 1
                if state["resolution"] is None:
                    state["status"] = "hypothese" if report.get("candidates") else "ungeloest"
            if kind == "failure" and state["resolution"] is None:
                state["status"] = "ungeloest"
            if kind == "resolution":
                state["resolution"] = dict(p, recorded_at=row["recorded_at"])
                state["status"] = p["case_status"]
        return state

    def cases(self):
        return [self.case(r["case_id"]) for r in self.events() if r["kind"] == "intake"]

    def begin(self, case_id):
        with self._lock():
            self.case(case_id)
            self._append(case_id, "begin", {})

    def failure(self, case_id, reason):
        with self._lock():
            self._append(case_id, "failure", {"reason": reason})

    def record_analysis(self, case_id, path):
        envelope = read_frozen(path)
        with self._lock():
            self.case(case_id)
            self._append(case_id, "analysis", {"frozen": envelope, "ranking_path": str(path)})

    def resolve(self, case_id, resolution):
        if (
            not resolution.get("asset_id")
            or not resolution.get("name")
            or not resolution.get("source")
            or not resolution.get("error_analysis")
        ):
            raise ValueError("resolution needs asset_id, name, source and error_analysis")
        if resolution.get("basis") not in ("user", "primary_source"):
            raise ValueError("resolution basis must be user or primary_source")
        if resolution.get("call_wkn") and not re.fullmatch(r"[A-Z0-9]{6}", resolution["call_wkn"]):
            raise ValueError("invalid call WKN format")
        with self._lock():
            state = self.case(case_id)
            first = state["first_prediction"]
            if first is None:
                raise ValueError("freeze first prediction before resolution")
            ranks = [c.get("asset_id") for c in first.get("candidates", [])[:3]]
            rank = (
                ranks.index(resolution["asset_id"]) + 1 if resolution["asset_id"] in ranks else None
            )
            selected = first.get("identification", {}).get("status") == "identified"
            p = dict(
                resolution,
                correct_rank=rank,
                prediction_outcome="confirmed"
                if rank == 1
                else "refuted"
                if ranks
                else "not_identified",
                product_verification="not_verified",
                original_call_status="original_reported_by_user"
                if resolution.get("basis") == "user" and resolution.get("call_wkn")
                else "original_reported_by_source"
                if resolution.get("call_wkn")
                else "unknown",
                case_status="bestaetigt"
                if rank == 1
                else "widerlegt"
                if selected or ranks
                else "bestaetigt",
            )
            self._append(case_id, "resolution", p)
            return p

    def export_register(self, path):
        # Post-analysis writer only; never called by the ranking engine.
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock(), path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            existing = handle.read()
            added = 0
            for row in self.events():
                if row["kind"] not in ("intake", "analysis", "resolution", "failure"):
                    continue
                marker = f"<!-- TI-JOURNAL:{row['sha256']} -->"
                if marker in existing:
                    continue
                payload = dict(row["payload"])
                if row["kind"] == "intake":
                    payload["input"] = {
                        k: v
                        for k, v in payload["input"].items()
                        if k not in ("screenshot_base64", "pdf_base64")
                    }
                if row["kind"] == "analysis":
                    report = payload["frozen"]["report"]
                    payload = {
                        "ranking_sha256": payload["frozen"]["sha256"],
                        "first_top3_unchanged": True,
                        "report": {
                            k: report.get(k)
                            for k in (
                                "run_id",
                                "case_id",
                                "headline",
                                "identification",
                                "candidates",
                                "criteria",
                                "limitations",
                                "source_timing",
                            )
                        },
                    }
                safe = (
                    json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    .replace("`", "\\u0060")
                    .replace("<", "\\u003c")
                )
                handle.seek(0, os.SEEK_END)
                handle.write(
                    f"\n\n{marker}\n### {row['case_id']} – {row['kind']} – {row['recorded_at']}\n"
                    f"\n```json\n{safe}\n```\n"
                )
                added += 1
            handle.flush()
            os.fsync(handle.fileno())
            return {"appended_events": added, "journal": self.verify()}

    def quality(self):
        rows = []
        for case in self.cases():
            first = case["first_prediction"]
            if first is None:
                continue
            resolution = case["resolution"]
            meta = case["input"]
            classification = meta.get("evaluation_class", "unclassified")
            independent = False
            preregistered = datetime.fromisoformat(case["opened_at"]) <= datetime.fromisoformat(
                case["first_frozen_at"]
            )
            pending = (
                preregistered
                and classification == "prospective_blind"
                and meta.get("previously_used_for_development") is False
                and bool(first.get("teaser_sha256"))
                and resolution is None
            )
            if classification == "prospective_blind" and resolution:
                try:
                    confirmed = datetime.fromisoformat(
                        resolution["confirmed_at"].replace("Z", "+00:00")
                    )
                    frozen = datetime.fromisoformat(case["first_frozen_at"])
                    independent = (
                        preregistered
                        and confirmed.utcoffset() is not None
                        and confirmed > frozen
                        and confirmed <= datetime.fromisoformat(resolution["recorded_at"])
                        and meta.get("previously_used_for_development") is False
                        and resolution.get("original_sha256") == first.get("teaser_sha256")
                        and bool(first.get("teaser_sha256"))
                        and bool(resolution.get("source"))
                    )
                except (ValueError, KeyError, TypeError):
                    pass
            if independent:
                classification = "independent"
            elif pending:
                classification = "independent_pending"
            rank = resolution.get("correct_rank") if resolution else None
            rows.append(
                {
                    "case_id": case["case_id"],
                    "evaluation_class": classification,
                    "opened_at": case["opened_at"],
                    "original_top3": first.get("candidates", [])[:3],
                    "resolved": bool(resolution),
                    "correct_rank": rank,
                    "top1_hit": rank == 1,
                    "top3_hit": rank is not None,
                    "false_identification": bool(
                        resolution
                        and first.get("identification", {}).get("status") == "identified"
                        and rank != 1
                    ),
                    "analysis_seconds": first.get("analysis_seconds"),
                    "source_quality": first.get("source_quality", {}),
                    "countercandidate_count": first.get("countercandidate_count"),
                    "resolution": resolution,
                }
            )

        def summary(items, allow_rates=False):
            graded = sum(r["resolved"] for r in items)
            total = len(items)
            unresolved = total - graded
            times = [
                r["analysis_seconds"]
                for r in items
                if isinstance(r["analysis_seconds"], (float, int))
            ]
            one = sum(r["top1_hit"] for r in items)
            three = sum(r["top3_hit"] for r in items)
            return {
                "total": total,
                "resolved_denominator": graded,
                "unresolved": unresolved,
                "top1_hits": one,
                "top3_hits": three,
                "false_identifications": sum(r["false_identification"] for r in items),
                "top1_rate": one / graded if allow_rates and graded else None,
                "top3_rate": three / graded if allow_rates and graded else None,
                "unresolved_fraction": unresolved / total if total else None,
                "average_research_seconds": sum(times) / len(times) if times else None,
                "rate_basis": "first_top3_among_resolved_independent_cases"
                if allow_rates and graded
                else "no_validated_independent_denominator",
                "source_documents": sum(r["source_quality"].get("documents", 0) for r in items),
                "primary_documents": sum(
                    r["source_quality"].get("primary_documents", 0) for r in items
                ),
            }

        return {
            "journal": self.verify(),
            "cases": rows,
            "all": summary(rows),
            "independent": summary(
                [
                    r
                    for r in rows
                    if r["evaluation_class"] in ("independent", "independent_pending")
                ],
                True,
            ),
            "development_regression": summary(
                [r for r in rows if r["evaluation_class"] == "development_regression"]
            ),
            "quality_over_time": [
                {
                    "case_id": r["case_id"],
                    "opened_at": r["opened_at"],
                    "evaluation_class": r["evaluation_class"],
                    "resolved": r["resolved"],
                    "correct_rank": r["correct_rank"],
                }
                for r in rows
            ],
            "warning": (
                "Counts use unchanged first rankings. Prospective independence requires "
                "operator provenance; hashes are not external signatures."
            ),
        }
