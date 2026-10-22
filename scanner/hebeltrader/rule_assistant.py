"""Conservative, read-only rule suggestions; every result requires human review.

Confidence labels describe matching heuristics, never probabilities. Drafts are
intentionally incomplete and cannot serve as approved backtest rules.
"""

import hashlib
import re
from collections import Counter
from datetime import datetime


def _normal(text):
    return " ".join(text.split())


def suggest_rules(doc, rec, *, run_at: datetime) -> dict:
    if not isinstance(run_at, datetime) or run_at.utcoffset() is None:
        raise ValueError("run_at must be timezone-aware")
    hints = []
    candidates = []
    draft = dict(
        document_sha=doc.sha256,
        ordinal=rec.ordinal,
        evidence=[],
        reviewer=None,
        reviewed_at=None,
        requires_manual_review=True,
        review_status="pending",
        provenance={
            "assistant_version": "1.4",
            "generated_at": run_at.isoformat(),
            "confidence": "heuristic_not_probability",
            "scope": "unverified",
        },
    )
    result = dict(
        document_sha=doc.sha256,
        ordinal=rec.ordinal,
        run_at=run_at.isoformat(),
        candidates=candidates,
        rules_json_candidate=draft,
        review_hints=hints,
        requires_manual_review=True,
    )

    def finish():
        result["counters"] = dict(Counter(c["kind"] for c in candidates))
        result["missing_fields"] = [
            f for f in ("partial_fraction", "after_target1", "exit_after") if f not in draft
        ]
        return result

    original = getattr(doc, "original_pdf", None)
    if (
        not isinstance(original, (bytes, bytearray, memoryview))
        or hashlib.sha256(original).hexdigest() != doc.sha256
        or rec.document_sha != doc.sha256
    ):
        hints.append("original_sha_mismatch")
        return finish()

    pages = {p["number"]: _normal(p.get("text", "")) for p in (doc.pages or [])}
    region_texts = {}
    for source_page in doc.pages or []:
        sequences = []
        for region in source_page.get("regions", []):
            lines = region.get("lines", []) if isinstance(region, dict) else region
            if isinstance(lines, list):
                sequences.append(
                    _normal(
                        " ".join(
                            line.get("text", "") if isinstance(line, dict) else str(line)
                            for line in lines
                        )
                    )
                )
        region_texts[source_page["number"]] = sequences
    evidence = getattr(rec, "evidence", None) or {}
    bound_pages = {
        e.get("page")
        for items in evidence.values()
        if isinstance(items, list)
        for e in items
        if isinstance(e, dict)
    }

    def add(kind, value, page, quote, *, bbox=None, confidence="medium", local_hints=None):
        scope = "source_page_unverified" if page in bound_pages else "document_unverified"
        notes = list(local_hints or []) + ["scope_requires_manual_review"]
        if bound_pages and page not in bound_pages:
            notes.append("cross_instrument_page_possible")
            confidence = "low"
        item = dict(
            page=page,
            quote=quote,
            fields=[kind],
            scope=scope,
            document_sha=doc.sha256,
            ordinal=rec.ordinal,
        )
        if bbox is not None:
            item["bbox"] = bbox
        candidates.append(
            dict(kind=kind, value=value, evidence=[item], confidence=confidence, review_hints=notes)
        )

    for field in ("derivative_target1", "derivative_target2", "stock_target1", "stock_target2"):
        value = getattr(rec, field, None)
        if value is None:
            continue
        for ev in evidence.get(field, []):
            if not isinstance(ev, dict):
                continue
            quote = _normal(ev.get("text") or ev.get("raw") or "")
            if quote and (
                quote in pages.get(ev.get("page"), "")
                or any(quote in text for text in region_texts.get(ev.get("page"), []))
            ):
                add(field, str(value), ev["page"], quote, bbox=ev.get("bbox"))

    target1 = r"(?:ziel\s*1|erst(?:en|e|es)?\s+(?:kurs)?ziel|ersten\s+zielkurs)"
    for page, text in pages.items():
        # Keep entire literal sentences, normalizing whitespace only.
        for quote in re.split(r"(?<=[.!?])\s+", text):
            low = quote.lower()
            if not low:
                continue
            negative = bool(re.search(r"\b(?:nicht|kein\w*)\b", low))
            if re.search(r"(?:50\s*%|hälfte|hälftig)", low) and re.search(
                r"verkauf|teilverkauf|reduzier", low
            ):
                partial_hints = []
                if negative:
                    partial_hints.append("negation_requires_review")
                if not re.search(target1, low):
                    partial_hints.append("partial_trigger_unverified")
                add(
                    "partial_fraction",
                    0.5 if not partial_hints else {"status": "unknown", "fraction": 0.5},
                    page,
                    quote,
                    local_hints=partial_hints,
                )
            if re.search(r"stop+p?", low):
                stop_values = []
                if re.search(r"(?:auf|zum)\s+(?:den\s+)?einstand|einstandskurs", low):
                    stop_values.append("entry")
                if re.search(r"(?:auf|zum)\s+(?:den\s+)?(?:zweiten\s+stop+p?|stop+p?\s*2)", low):
                    stop_values.append("stop2")
                if "unverändert" in low:
                    stop_values.append("unchanged")
                for value in stop_values:
                    explicit = bool(re.search(target1, low)) and not negative
                    add(
                        "after_target1",
                        value if explicit else {"status": "unknown", "mentioned_stop": value},
                        page,
                        quote,
                        local_hints=[] if explicit else ["target1_trigger_unverified"],
                    )
            duration = re.search(
                r"\b(?:nach|spätestens(?:\s+nach)?|maximal|höchstens)\s+(\d+)\s*[-–]?\s*(handels(?:tagen?|tage)|kalendertagen?|tagen?)\b",
                low,
            )
            if duration:
                days = int(duration.group(1))
                unit_text = duration.group(2)
                unit = (
                    "trading_sessions"
                    if unit_text.startswith("handels")
                    else "calendar_days"
                    if unit_text.startswith("kalender")
                    else None
                )
                conditional = bool(
                    re.search(r"\bohne\b|\bfalls\b|\bwenn\b|sofern|solange|nicht\s+erreicht", low)
                )
                exits = bool(
                    re.search(
                        r"schließ|schliess|verkauf|beend|glattstell|ausstieg|ausgestiegen", low
                    )
                )
                notes = []
                if unit is None:
                    notes.append("ambiguous_time_unit")
                if conditional:
                    notes.append("unmodeled_temporal_condition")
                if not exits:
                    notes.append("holding_duration_not_explicit_exit")
                value = dict(days=days, unit=unit)
                if notes or days <= 0 or negative:
                    value["status"] = "unknown"
                add("exit_after", value, page, quote, local_hints=notes)
    if re.search(r"put|short", getattr(rec, "product_type", "") or "", re.I):
        hints.append("short_direction_requires_review")
        for candidate in candidates:
            candidate["confidence"] = "low"
            candidate["review_hints"].append("short_direction_requires_review")
    for field in ("partial_fraction", "after_target1", "exit_after"):
        items = [c for c in candidates if c["kind"] == field]
        supported = [
            c
            for c in items
            if not isinstance(c["value"], dict) or c["value"].get("status") != "unknown"
        ]
        values = {repr(c["value"]) for c in supported}
        if len(values) > 1:
            hints.append("contradictory_" + field)
            for candidate in items:
                candidate["confidence"] = "low"
                candidate["review_hints"].append("contradictory_" + field)
        elif supported and len(supported) == len(items):
            draft[field] = supported[0]["value"]
            draft["evidence"].extend(e for c in supported for e in c["evidence"])
    layout_hints = suggest_layout_rule_hints(doc, rec)
    result["layout_rule_candidates"] = layout_hints
    for field in ("partial_fraction", "after_target1", "target2_sale", "conditional_loss_exit"):
        items = [c for c in layout_hints if c["kind"] == field]
        values = {repr(c["value"]) for c in items}
        if len(values) == 1:
            # Separate scoped candidates remain available even if manual scope binding is needed.
            draft[field] = items[0]["value"]
            draft["evidence"].extend(e for c in items for e in c["evidence"])
        elif len(values) > 1:
            draft.pop(field, None)
            hints.append("contradictory_layout_" + field)
    return finish()


def suggest_layout_rule_hints(doc, rec):
    """Recognize cited column-local prose; never promotes it to executable rules."""
    if hashlib.sha256(doc.original_pdf).hexdigest() != doc.sha256 or rec.document_sha != doc.sha256:
        return []
    candidates = []
    for page in doc.pages:
        for region_index, region in enumerate(page.get("regions", [])):
            lines = region.get("lines", []) if isinstance(region, dict) else region
            if any(not isinstance(line, dict) or "bbox" not in line for line in lines):
                continue
            groups = []
            for line in lines:
                if not groups or line["bbox"][1] - groups[-1][-1]["bbox"][3] > 18:
                    groups.append([])
                groups[-1].append(line)
            for group in groups:
                raw = _normal(" ".join(line["text"] for line in group))
                sentences = re.split(r"(?<=[.!?])\s+", raw)
                previous = ""
                for sentence in sentences:
                    # Matching is dehyphenated; evidence is the untouched source sequence.
                    match_text = re.sub(r"(?<=\w)-\s+(?=\w)", "", sentence).casefold()
                    context = re.sub(r"(?<=\w)-\s+(?=\w)", "", previous).casefold()
                    scope_text = context + " " + match_text
                    scope = (
                        "derivative_mentioned"
                        if "derivat" in scope_text
                        else "stock_mentioned"
                        if re.search(r"aktien?\b", scope_text)
                        else "instrument_unverified"
                    )

                    def add_hint(
                        kind,
                        value,
                        quote,
                        notes=(),
                        *,
                        scope=scope,
                        page=page,
                        group=group,
                        region_index=region_index,
                    ):
                        candidates.append(
                            dict(
                                kind=kind,
                                value=value,
                                instrument_scope=scope,
                                confidence="medium",
                                requires_manual_review=True,
                                review_hints=["scope_requires_manual_review", *notes],
                                evidence=[
                                    dict(
                                        page=page["number"],
                                        quote=quote,
                                        bbox=[
                                            min(r["bbox"][0] for r in group),
                                            min(r["bbox"][1] for r in group),
                                            max(r["bbox"][2] for r in group),
                                            max(r["bbox"][3] for r in group),
                                        ],
                                        region=region_index,
                                        document_sha=doc.sha256,
                                        ordinal=rec.ordinal,
                                        fields=[kind],
                                    )
                                ],
                            )
                        )

                    negated = bool(re.search(r"\b(?:nicht|kein\w*)\b", match_text))
                    first = bool(
                        re.search(r"erste[nsrm]?\s+kursziel|kursziel\s*1|ziel\s*1", match_text)
                    )
                    if first and "hälfte" in match_text and "verkauf" in match_text and not negated:
                        add_hint("partial_fraction", 0.5, sentence)
                    if (
                        "stopp" in match_text
                        and re.search(
                            r"einstands?kurs|einstand|einstiegskurs|"
                            r"auf den wert des ersten kursziels",
                            match_text,
                        )
                        and (
                            first
                            or (
                                "dann" in match_text
                                and re.search(r"erste[nsrm]?\s+kursziel|kursziel\s*1", context)
                            )
                        )
                        and not negated
                    ):
                        add_hint(
                            "after_target1",
                            "target1"
                            if "auf den wert des ersten kursziels" in match_text
                            else "entry",
                            (previous + " " + sentence).strip(),
                        )
                    if (
                        re.search(r"kursziel\s*2|zweite[nsrm]?\s+kursziel", match_text)
                        and "hälfte" in match_text
                        and "verkauf" in match_text
                        and not negated
                    ):
                        add_hint("target2_sale", dict(fraction=0.5, trigger="target2"), sentence)
                    duration = re.search(r"\b(\d+)\s+(handels|kalender)?tagen?\b", match_text)
                    if (
                        duration
                        and "im minus" in match_text
                        and "geschlossen" in match_text
                        and not negated
                    ):
                        unit = {"handels": "trading_sessions", "kalender": "calendar_days"}.get(
                            duration[2]
                        )
                        add_hint(
                            "conditional_loss_exit",
                            dict(
                                days=int(duration[1]),
                                unit=unit,
                                condition="position_in_loss",
                                threshold="at_least"
                                if "oder länger" in match_text
                                else "unspecified",
                            ),
                            sentence,
                            ["time_unit_unverified"] if unit is None else [],
                        )
                    previous = sentence
    return candidates
