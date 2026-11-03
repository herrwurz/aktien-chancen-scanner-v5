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
        intake_input = rows[0]["payload"]["input"]
        state = {
            "case_id": case_id,
            "status": "neu",
            "input": intake_input,
            "input_sha256": rows[0]["payload"]["input_sha256"],
            "first_prediction": None,
            "latest_prediction": None,
            "resolution": None,
            "archived": False,
            "archive": None,
            "deleted": False,
            "delete": None,
            "reference_status": None,
            "evaluation_class": intake_input.get("evaluation_class", "unclassified"),
            "competition_mode": intake_input.get("competition_mode") or "official",
            "previously_used_for_development": intake_input.get("previously_used_for_development"),
            "solution_pdf": None,
            "listing_promotion": None,
            "dataset_promotion": None,
            "analyses": 0,
            "opened_at": rows[0]["recorded_at"],
            "first_frozen_at": None,
        }
        for row in rows:
            kind, p = row["kind"], row["payload"]
            if kind in ("intake", "input_revision"):
                mode = (p.get("input") or {}).get("competition_mode")
                if mode in ("official", "out_of_competition"):
                    state["competition_mode"] = mode
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
            if kind == "archive":
                state["archived"] = True
                state["archive"] = dict(p, recorded_at=row["recorded_at"])
            if kind == "restore":
                state["archived"] = False
                state["archive"] = None
            if kind == "delete":
                state["deleted"] = True
                state["delete"] = dict(p, recorded_at=row["recorded_at"])
            if kind == "reference_promotion":
                state["reference_status"] = "prospective_reference"
            if kind == "prospective_classification":
                state["evaluation_class"] = "prospective_blind"
                state["previously_used_for_development"] = False
            if kind == "solution_pdf":
                state["solution_pdf"] = dict(p, recorded_at=row["recorded_at"])
            if kind == "listing_promotion":
                mode = p.get("competition_mode")
                if mode in ("official", "out_of_competition"):
                    state["competition_mode"] = mode
                state["listing_promotion"] = dict(p, recorded_at=row["recorded_at"])
            if kind == "dataset_promotion":
                state["dataset_promotion"] = dict(p, recorded_at=row["recorded_at"])
        # Invariant: a purchased report ends außer-Konkurrenz, even if an older
        # journal is missing the listing_promotion event (heal on read).
        if state.get("solution_pdf") and state.get("competition_mode") == "out_of_competition":
            state["competition_mode"] = "official"
            if not state.get("listing_promotion"):
                state["listing_promotion"] = {
                    "competition_mode": "official",
                    "reason": "solution_pdf_uploaded",
                    "pdf_sha256": state["solution_pdf"].get("pdf_sha256"),
                    "recorded_at": state["solution_pdf"].get("recorded_at"),
                    "inferred": True,
                }
        return state

    def cases(self, include_archived=False, *, listing="official"):
        """List cases for the operator UI.

        listing:
          - official: default Meine Fälle (excludes out_of_competition)
          - out_of_competition: only außer-Konkurrenz cases
          - all: both modes
        """
        if listing not in ("official", "out_of_competition", "all"):
            raise ValueError("listing must be official, out_of_competition, or all")
        rows = [self.case(r["case_id"]) for r in self.events() if r["kind"] == "intake"]
        rows = [row for row in rows if not row.get("deleted")]
        if not include_archived:
            rows = [row for row in rows if not row["archived"]]
        if listing == "official":
            return [row for row in rows if row.get("competition_mode", "official") == "official"]
        if listing == "out_of_competition":
            return [row for row in rows if row.get("competition_mode") == "out_of_competition"]
        return rows

    def archive(self, case_id, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("archive reason required")
        with self._lock():
            state = self.case(case_id)
            if state.get("deleted"):
                raise ValueError("deleted case cannot be archived")
            if state["archived"]:
                return state["archive"]
            return self._append(case_id, "archive", {"reason": reason.strip()})["payload"]

    def restore(self, case_id, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("restore reason required")
        with self._lock():
            state = self.case(case_id)
            if state.get("deleted"):
                raise ValueError("deleted case cannot be restored")
            if not state["archived"]:
                return {"archived": False}
            self._append(case_id, "restore", {"reason": reason.strip()})
            return {"archived": False}

    def delete(self, case_id, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("delete reason required")
        with self._lock():
            state = self.case(case_id)
            if state.get("deleted"):
                return state.get("delete") or {"deleted": True}
            return self._append(case_id, "delete", {"reason": reason.strip()})["payload"]

    def references(self):
        # Official listing only — out-of-competition cases never enter the blind register.
        promoted = [row for row in self.cases(True, listing="official") if row["reference_status"]]
        return [dict(row, reference_number=19 + index) for index, row in enumerate(promoted)]

    def promote_reference(self, case_id, source):
        if not isinstance(source, str) or not source.strip():
            raise ValueError("reference source required")
        with self._lock():
            state = self.case(case_id)
            if state.get("competition_mode") == "out_of_competition":
                raise ValueError("out_of_competition cases cannot become prospective references")
            if state["reference_status"]:
                return {"reference_status": state["reference_status"]}
            if state["resolution"] is None:
                raise ValueError("resolved case required")
            if state["evaluation_class"] != "prospective_blind":
                raise ValueError("prospective blind case required")
            self._append(
                case_id,
                "reference_promotion",
                {"source": source.strip(), "reference_status": "prospective_reference"},
            )
            return {"reference_status": "prospective_reference"}

    def mark_prospective(self, case_id, basis):
        if not isinstance(basis, str) or not basis.strip():
            raise ValueError("classification basis required")
        with self._lock():
            state = self.case(case_id)
            if state.get("competition_mode") == "out_of_competition":
                raise ValueError("out_of_competition cases cannot be marked prospective blind")
            if state["resolution"] is not None:
                raise ValueError("resolved case cannot be reclassified")
            if state["first_prediction"] is None:
                raise ValueError("frozen prediction required")
            if state["evaluation_class"] == "prospective_blind":
                return {"evaluation_class": "prospective_blind"}
            self._append(case_id, "prospective_classification", {"basis": basis.strip()})
            return {"evaluation_class": "prospective_blind"}

    def _has_listing_promotion_event(self, case_id):
        return any(
            row["case_id"] == case_id and row["kind"] == "listing_promotion"
            for row in self.events()
        )

    def _append_listing_promotion(self, case_id, pdf_sha256):
        return self._append(
            case_id,
            "listing_promotion",
            {
                "competition_mode": "official",
                "reason": "solution_pdf_uploaded",
                "pdf_sha256": pdf_sha256,
            },
        )

    def store_solution_pdf(self, case_id, pdf_bytes, *, extracted=None):
        """Persist a purchased-report PDF under the journal root (not git).

        Uploading a solution PDF moves out-of-competition cases into the official
        listing (Meine Fälle / quality), because the operator now has the report.
        """
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes:
            raise ValueError("solution PDF bytes required")
        sha = hashlib.sha256(bytes(pdf_bytes)).hexdigest()
        with self._lock():
            state = self.case(case_id)
            existing = state.get("solution_pdf") or {}
            if existing.get("pdf_sha256") == sha:
                # Durable audit event if an older journal only had the PDF.
                if not self._has_listing_promotion_event(case_id):
                    self._append_listing_promotion(case_id, sha)
                result = {k: v for k, v in existing.items() if k != "recorded_at"}
                # Invariant: stored report ⇒ official listing.
                result["listed_as_official"] = True
                return result
            pdf_dir = self.root / "solution-pdfs" / case_id
            pdf_dir.mkdir(parents=True, exist_ok=True)
            path = pdf_dir / f"{sha}.pdf"
            if not path.exists():
                partial = path.with_suffix(".partial")
                partial.write_bytes(bytes(pdf_bytes))
                partial.replace(path)
            payload = {
                "pdf_sha256": sha,
                "relative_path": str(path.relative_to(self.root)),
                "byte_length": len(pdf_bytes),
                "extracted": extracted or {},
            }
            self._append(case_id, "solution_pdf", payload)
            if not self._has_listing_promotion_event(case_id):
                self._append_listing_promotion(case_id, sha)
            # Official whenever a report is on file (new upload always lists).
            payload["listed_as_official"] = True
            return payload

    def promote_to_dataset(self, case_id, promotion):
        """Explicit operator action: export case + stored PDF into a local dataset record.

        Typically used after a purchased-report PDF moved an OOC teaser into listing.
        Does not mutate git-tracked teaser-cases.json or featured_calls.json.
        """
        if not isinstance(promotion, dict):
            raise ValueError("dataset promotion payload required")
        name = promotion.get("name")
        source = promotion.get("source")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("dataset promotion needs name")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("dataset promotion needs source")
        call_wkn = promotion.get("call_wkn")
        if call_wkn and not re.fullmatch(r"[A-Z0-9]{6}", str(call_wkn)):
            raise ValueError("invalid call WKN format")
        with self._lock():
            state = self.case(case_id)
            if state.get("dataset_promotion"):
                return {k: v for k, v in state["dataset_promotion"].items() if k != "recorded_at"}
            if not state.get("solution_pdf"):
                raise ValueError("solution PDF required before dataset promotion")
            if state.get("resolution") is None:
                raise ValueError("resolve the case before dataset promotion")
            export_dir = self.root / "dataset-exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            export_path = export_dir / f"{case_id}.json"
            record = {
                "schema_version": 1,
                "kind": "hebeltrader_report_dataset_export",
                "case_id": case_id,
                "competition_mode": state.get("competition_mode") or "official",
                "listing_promotion": state.get("listing_promotion"),
                "promoted_at": self.clock().isoformat(),
                "headline": (state.get("input") or {}).get("headline") or "",
                "teaser_text": (state.get("input") or {}).get("teaser_text") or "",
                "issue": (state.get("input") or {}).get("issue") or "",
                "author": (state.get("input") or {}).get("author") or "",
                "actual_company": name.strip(),
                "actual_ticker": (promotion.get("ticker") or "").strip() or None,
                "stock_wkn": (promotion.get("stock_wkn") or "").strip() or None,
                "derivative_wkn": call_wkn or state["resolution"].get("call_wkn"),
                "source": source.strip(),
                "notes": (promotion.get("notes") or "").strip() or None,
                "solution_pdf": {
                    "pdf_sha256": state["solution_pdf"].get("pdf_sha256"),
                    "relative_path": state["solution_pdf"].get("relative_path"),
                },
                "resolution": {
                    "asset_id": state["resolution"].get("asset_id"),
                    "name": state["resolution"].get("name"),
                    "correct_rank": state["resolution"].get("correct_rank"),
                    "prediction_outcome": state["resolution"].get("prediction_outcome"),
                    "case_status": state["resolution"].get("case_status"),
                },
                "original_top3": (state.get("first_prediction") or {}).get("candidates", [])[:3],
                "git_note": (
                    "Local export only. Operator may copy into teaser-cases.json manually; "
                    "this path is never auto-committed."
                ),
            }
            export_path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            )
            payload = {
                "export_relative_path": str(export_path.relative_to(self.root)),
                "name": name.strip(),
                "ticker": record["actual_ticker"],
                "stock_wkn": record["stock_wkn"],
                "call_wkn": record["derivative_wkn"],
                "source": source.strip(),
                "pdf_sha256": state["solution_pdf"].get("pdf_sha256"),
            }
            self._append(case_id, "dataset_promotion", payload)
            return payload

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
        ):
            raise ValueError("resolution needs asset_id, name and source")
        if resolution.get("basis") not in ("user", "primary_source"):
            raise ValueError("resolution basis must be user or primary_source")
        if resolution.get("call_wkn") and not re.fullmatch(r"[A-Z0-9]{6}", resolution["call_wkn"]):
            raise ValueError("invalid call WKN format")
        with self._lock():
            state = self.case(case_id)
            if state.get("deleted"):
                raise ValueError("deleted case cannot be resolved")
            first = state["first_prediction"]
            if first is None:
                raise ValueError("freeze first prediction before resolution")
            payload = dict(resolution)
            if not str(payload.get("error_analysis") or "").strip():
                from .resolution import draft_error_analysis

                payload["error_analysis"] = draft_error_analysis(
                    first,
                    resolved_name=payload.get("name"),
                    resolved_asset_id=payload.get("asset_id"),
                )
            ranks = [c.get("asset_id") for c in first.get("candidates", [])[:3]]
            rank = ranks.index(payload["asset_id"]) + 1 if payload["asset_id"] in ranks else None
            selected = first.get("identification", {}).get("status") == "identified"
            p = dict(
                payload,
                correct_rank=rank,
                prediction_outcome="confirmed"
                if rank == 1
                else "refuted"
                if ranks
                else "not_identified",
                product_verification="not_verified",
                original_call_status="original_reported_by_user"
                if payload.get("basis") == "user" and payload.get("call_wkn")
                else "original_reported_by_source"
                if payload.get("call_wkn")
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
                if row["kind"] not in (
                    "intake",
                    "analysis",
                    "resolution",
                    "failure",
                    "archive",
                    "restore",
                    "delete",
                    "prospective_classification",
                    "reference_promotion",
                    "solution_pdf",
                    "listing_promotion",
                    "dataset_promotion",
                ):
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
            classification = case["evaluation_class"]
            independent = False
            preregistered = datetime.fromisoformat(case["opened_at"]) <= datetime.fromisoformat(
                case["first_frozen_at"]
            )
            pending = (
                preregistered
                and classification == "prospective_blind"
                and case["previously_used_for_development"] is False
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
                        and case["previously_used_for_development"] is False
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
