import base64
import binascii
import hashlib
import re
from datetime import UTC, datetime

from scanner.research import AssetIdentity, EvidenceRecord

from .catalog import CATALOG_REVISION, default_candidate_source, load_products
from .clue_enrichment import HeuristicClueEnricher
from .clues import extract_atomic_clues, extract_clues
from .documents import extract_document
from .hypothesis import decide_hypothesis, hypothesis_reasons, select_hypothesis_candidates
from .ocr import TesseractOcr
from .schemas import SourceSpan
from .verification import decide, verify_candidates

MAX_RESPONSE_EVIDENCE = 8


def _phrase_present(text, phrase):
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.I) is not None


class DetectiveService:
    def __init__(
        self,
        *,
        ocr=None,
        candidate_source=None,
        news_source=None,
        products=None,
        clock=None,
        research_mode="fixture",
        enricher=None,
    ):
        self.ocr = ocr or TesseractOcr()
        # Default stays on the legacy fixture source (no retrieve_candidates) so MVP
        # ranking/API compatibility tests keep working. Factory wraps hypothesis mode.
        self.candidate_source = candidate_source or default_candidate_source()
        self.news_source = news_source or self.candidate_source
        self.products = products if products is not None else load_products()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.research_mode = research_mode
        self.enricher = enricher or HeuristicClueEnricher()

    def analyze(self, request):
        text_parts = []
        input_sources = []
        review_hints = []
        if request.teaser_text.strip():
            text_parts.append(("teaser_text", None, request.teaser_text.strip()))
            input_sources.append({"type": "teaser_text", "characters": len(request.teaser_text)})
        for index, hint in enumerate(request.known_hints):
            text_parts.append((f"known_hint:{index}", None, hint))
        image_sha = None
        if request.screenshot_base64:
            try:
                image = base64.b64decode(request.screenshot_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("invalid screenshot base64") from None
            image_sha = hashlib.sha256(image).hexdigest()
            ocr_text = self.ocr.extract(image, request.screenshot_media_type)
            text_parts.append(("screenshot_ocr", None, ocr_text))
            input_sources.append(
                {
                    "type": "screenshot_ocr",
                    "sha256": image_sha,
                    "media_type": request.screenshot_media_type,
                    "engine": self.ocr.engine,
                    "characters": len(ocr_text),
                }
            )
            review_hints.append("OCR text requires visual review against the original screenshot")
        if request.pdf_base64:
            try:
                pdf = base64.b64decode(request.pdf_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("invalid PDF base64") from None
            document = extract_document(pdf, request.pdf_media_type, ocr=self.ocr)
            offset_pages = []
            for page in document.pages:
                if page.text:
                    text_parts.append((f"pdf:{document.sha256}", page.number, page.text))
                offset_pages.append(page.model_dump(mode="json"))
            input_sources.append(
                {
                    "type": "pdf",
                    "sha256": document.sha256,
                    "media_type": document.media_type,
                    "page_count": document.page_count,
                    "complete": document.complete,
                    "pages": offset_pages,
                }
            )
            if not document.complete or any(page.requires_manual_review for page in document.pages):
                review_hints.append("PDF extraction requires review against the original pages")
        combined_parts, spans, cursor = [], [], 0
        for source_id, page, value in text_parts:
            if not value:
                continue
            if combined_parts:
                cursor += 1
            start = cursor
            combined_parts.append(value)
            cursor += len(value)
            spans.append(SourceSpan(source_id=source_id, page=page, start=start, end=cursor))
        combined = "\n".join(combined_parts)
        clues = extract_clues(combined)
        atomic_clues = extract_atomic_clues(combined, spans)
        enrichment = self.enricher.enrich(combined, atomic_clues, spans)
        if enrichment.extra_clues:
            atomic_clues = sorted(
                [*atomic_clues, *enrichment.extra_clues],
                key=lambda clue: (clue.start, clue.category, clue.clue_id),
            )
        if hasattr(self.candidate_source, "retrieve_candidates"):
            return self._analyze_v3(
                request,
                input_sources,
                review_hints,
                clues,
                atomic_clues,
                image_sha,
                enrichment,
            )
        ranked = self._rank(combined, clues, request.publication_at)
        decision = self._decision(ranked)
        derivative = self._find_derivative(clues, decision, request.publication_at)
        if request.publication_at is None:
            review_hints.append(
                "Publication timestamp missing; historical evidence and products cannot be verified"
            )
        if decision["status"] != "resolved_candidate":
            review_hints.append(decision["reason"])
        return {
            "schema_version": 3,
            "status": "candidate_identification_only",
            "strategy": "HEBELTRADER_DETECTIVE",
            "research_mode": self.research_mode,
            "analyzed_at": self.clock().isoformat(),
            "publication_at": (
                request.publication_at.isoformat() if request.publication_at else None
            ),
            "candidate_source": {
                "source_id": self.candidate_source.source_id,
                "coverage": self.candidate_source.coverage,
                "catalog_revision": CATALOG_REVISION,
            },
            "input_sources": input_sources,
            "extracted_clues": {
                key: value for key, value in clues.items() if key != "normalized_text"
            },
            "identification": decision,
            "candidates": ranked[:3],
            "derivative_candidate": derivative,
            "review_hints": review_hints,
            "identification_is_investment_recommendation": False,
            "automatic_confirmation": False,
            "observed_image_sha256": image_sha,
        }

    def _analyze_v3(
        self,
        request,
        input_sources,
        review_hints,
        legacy_clues,
        atomic_clues,
        image_sha,
        enrichment,
    ):
        stage_a_asset_ids = []
        analysis_mode = getattr(request, "analysis_mode", "hypothesis")
        as_of = request.publication_at
        if as_of is None and analysis_mode == "hypothesis":
            as_of = self.clock()
            review_hints.append(
                "hypothesis mode without publication_at uses analysis clock; not historical_blind"
            )
        if as_of is None:
            retrieval_status = "missing_publication_time"
            verified = []
            review_hints.append(
                "Publication timestamp missing; historical evidence and products cannot be verified"
            )
        else:
            retrieve = self.candidate_source.retrieve_candidates
            try:
                retrieval = retrieve(atomic_clues, as_of, search_queries=enrichment.search_queries)
            except TypeError:
                retrieval = retrieve(atomic_clues, as_of)
            retrieval_status = retrieval.status
            stage_a_asset_ids = [row.asset_id for row in retrieval.candidates]
            verified = verify_candidates(
                retrieval,
                atomic_clues,
                self.news_source.evidence_for,
                as_of,
            )
            if analysis_mode == "hypothesis":
                verified = sorted(
                    verified,
                    key=lambda row: (
                        bool(row.hard_contradictions),
                        -row.evidence_score,
                        -row.retrieval_score,
                        row.asset_id,
                    ),
                )
        if analysis_mode == "hypothesis":
            decision = decide_hypothesis(verified, retrieval_status, analysis_mode=analysis_mode)
            selected_rows = select_hypothesis_candidates(verified, decision)
        else:
            decision = decide(verified, retrieval_status)
            selected_rows = verified[:3]
        selected = next(
            (row for row in verified if row.asset_id == decision.selected_asset_id), None
        )
        derivative_decision = {"selected_wkn": selected.identity.get("wkn") if selected else None}
        derivative = self._find_derivative(
            legacy_clues, derivative_decision, request.publication_at
        )
        if decision.status not in {"likely_candidate", "hypothesis_top3"}:
            review_hints.append(decision.reason)
        review_hints.extend(enrichment.notes)
        clues_by_id = {clue.clue_id: clue for clue in atomic_clues}
        candidate_payloads = []
        for row in selected_rows:
            supporting = [
                {
                    "type": clues_by_id[clue_id].category,
                    "value": clues_by_id[clue_id].value or clues_by_id[clue_id].normalized,
                }
                for clue_id in row.confirmed_clue_ids
                if clue_id in clues_by_id
            ]
            contradictions = [
                {
                    "type": clues_by_id[clue_id].category,
                    "value": clues_by_id[clue_id].value or clues_by_id[clue_id].normalized,
                }
                for clue_id in row.contradicted_clue_ids
                if clue_id in clues_by_id
            ]
            candidate_payloads.append(
                {
                    **row.identity,
                    **row.model_dump(mode="json"),
                    "supporting_clues": supporting,
                    "hard_facts": [item for item in supporting if item["type"] == "identifier"],
                    "contradictions": contradictions,
                    "hypothesis_reasons": hypothesis_reasons(row),
                    "evidence_strength": (
                        "contradicted"
                        if contradictions
                        else "supported_uncalibrated"
                        if supporting
                        else "hypothesis_only"
                    ),
                    "relevance_score_not_probability": row.evidence_score,
                }
            )
        coverage = dict(getattr(self.candidate_source, "coverage", {}) or {})
        coverage.setdefault("stage_a_asset_ids", stage_a_asset_ids)
        coverage.setdefault("channel_limit", 50)
        coverage["search_queries"] = enrichment.search_queries
        coverage["enrichment_provider"] = enrichment.provider
        return {
            "schema_version": 3,
            "status": "candidate_identification_only",
            "strategy": "HEBELTRADER_DETECTIVE",
            "analysis_mode": analysis_mode,
            "research_mode": self.research_mode,
            "analyzed_at": self.clock().isoformat(),
            "publication_at": (
                request.publication_at.isoformat() if request.publication_at else None
            ),
            "candidate_source": {
                "source_id": self.candidate_source.source_id,
                "coverage": coverage,
                "catalog_revision": CATALOG_REVISION,
            },
            "input_sources": input_sources,
            "extracted_clues": [clue.model_dump(mode="json") for clue in atomic_clues],
            "search_queries": enrichment.search_queries,
            "identification": {
                **decision.model_dump(mode="json"),
                "selected_wkn": (
                    (selected.identity.get("wkn") if selected else None)
                    or (
                        selected_rows[0].identity.get("wkn")
                        if selected_rows and decision.status == "hypothesis_top3"
                        else None
                    )
                ),
                "failure_code": (decision.reason if decision.status == "unresolved" else None),
            },
            "candidates": candidate_payloads,
            "derivative_candidate": derivative,
            "review_hints": review_hints,
            "identification_is_investment_recommendation": False,
            "automatic_confirmation": False,
            "observed_image_sha256": image_sha,
        }

    def _rank(self, text, clues, point_in_time):
        ranked = []
        if hasattr(self.candidate_source, "search_candidates"):
            self.candidate_source.search_candidates(text, clues, point_in_time)
        for raw in self.candidate_source.load_candidates():
            identity = AssetIdentity.model_validate(raw["identity"])
            records = [
                EvidenceRecord.model_validate(row)
                for row in self.news_source.evidence_for(identity)
            ]
            eligible = (
                [record for record in records if record.available_at(point_in_time)]
                if point_in_time
                else []
            )
            future = [record.source_id for record in records if record not in eligible]
            hard_facts, supporting, contradictions = [], [], []
            identity_proven = bool(
                self.research_mode == "fixture"
                or (
                    point_in_time
                    and (
                        identity.historically_available_at(point_in_time)
                        or any(record.source_kind == "fixture" for record in eligible)
                    )
                )
            )
            if identity_proven and identity.wkn in clues["stock_wkn"]:
                hard_facts.append({"type": "exact_stock_wkn", "value": identity.wkn})
            if (
                identity_proven
                and identity.isin in clues["isins"]
                and identity.isin not in clues["invalid_isins"]
            ):
                hard_facts.append({"type": "valid_exact_stock_isin", "value": identity.isin})
            for alias in raw.get("aliases", []):
                if identity_proven and _phrase_present(text, alias):
                    hard_facts.append({"type": "bounded_name_or_alias", "value": alias})
            facts = {
                "sectors": set(),
                "countries": set(),
                "events": set(),
                "fact_claims": set(),
            }
            if point_in_time and identity.historically_available_at(point_in_time):
                if identity.sector:
                    facts["sectors"].add(identity.sector)
                if identity.country:
                    facts["countries"].add(identity.country)
            for record in eligible:
                for group in facts:
                    facts[group].update(record.facts.get(group, []))
            for group in facts:
                for value in clues["structured"][group]:
                    if value in facts[group]:
                        supporting.append({"type": group, "value": value})
                    elif group in {"countries", "sectors", "fact_claims"} and facts[group]:
                        contradictions.append(
                            {
                                "type": f"{group}_mismatch",
                                "value": value,
                                "candidate": sorted(facts[group]),
                            }
                        )
                for value in clues["negative"][group]:
                    if value in facts[group]:
                        contradictions.append({"type": f"negated_{group}", "value": value})
            if identity_proven and clues["stock_wkn"] and identity.wkn not in clues["stock_wkn"]:
                contradictions.append(
                    {"type": "different_explicit_stock_wkn", "value": clues["stock_wkn"]}
                )
            score = len(hard_facts) * 100 + len(supporting) * 12 - len(contradictions) * 30
            unverified = {
                group: [value for value in clues["structured"][group] if value not in facts[group]]
                for group in facts
            }
            if contradictions:
                strength = "contradicted"
            elif not eligible:
                strength = "insufficient_evidence"
            elif hard_facts or len(supporting) >= 2:
                strength = "supported_uncalibrated"
            else:
                strength = "limited_evidence"
            if not (hard_facts or supporting or contradictions):
                continue

            def response_relevance(record, candidate_facts=facts):
                matches = sum(
                    len(set(record.facts.get(group, [])) & set(clues["structured"][group]))
                    for group in candidate_facts
                )
                return (-matches, record.source_id)

            returned_evidence = sorted(eligible, key=response_relevance)[:MAX_RESPONSE_EVIDENCE]
            returned_future = future[:MAX_RESPONSE_EVIDENCE]
            ranked.append(
                {
                    **identity.model_dump(mode="json"),
                    "relevance_score_not_probability": score,
                    "evidence_strength": strength,
                    "hard_facts": hard_facts,
                    "supporting_clues": supporting,
                    "contradictions": contradictions,
                    "unverified_clues": unverified,
                    "eligible_evidence": [
                        record.model_dump(mode="json") for record in returned_evidence
                    ],
                    "evidence_summary": {
                        "eligible_total": len(eligible),
                        "returned": len(returned_evidence),
                        "omitted": len(eligible) - len(returned_evidence),
                        "response_limit": MAX_RESPONSE_EVIDENCE,
                    },
                    "excluded_future_or_unavailable_source_ids": returned_future,
                    "excluded_evidence_summary": {
                        "total": len(future),
                        "returned": len(returned_future),
                        "omitted": len(future) - len(returned_future),
                        "response_limit": MAX_RESPONSE_EVIDENCE,
                    },
                    "confirmed": False,
                    "missing_for_confirmation": [
                        "independent time-valid public evidence",
                        "manual identity review",
                    ],
                }
            )
        return sorted(
            ranked,
            key=lambda row: (
                row["evidence_strength"] == "contradicted",
                -row["relevance_score_not_probability"],
                row["name"],
            ),
        )

    @staticmethod
    def _decision(ranked):
        supported = [row for row in ranked if row["evidence_strength"] == "supported_uncalibrated"]
        if not supported:
            return {
                "status": "unresolved",
                "reason": "insufficient_evidence",
                "selected_wkn": None,
                "confidence": "not_calibrated",
            }
        if len(supported) > 1:
            margin = (
                supported[0]["relevance_score_not_probability"]
                - supported[1]["relevance_score_not_probability"]
            )
            if margin < 12:
                return {
                    "status": "unresolved",
                    "reason": "ambiguous_candidates",
                    "selected_wkn": None,
                    "confidence": "not_calibrated",
                }
        return {
            "status": "resolved_candidate",
            "reason": "strongest_supported_candidate_requires_manual_review",
            "selected_wkn": supported[0]["wkn"],
            "selected_identity": {
                key: supported[0].get(key) for key in ("name", "ticker", "wkn", "isin", "cik")
            },
            "confidence": "uncalibrated_evidence_strength",
        }

    def _find_derivative(self, clues, decision, point_in_time):
        requested = clues["derivative_wkn"]
        if not requested:
            return {
                "status": "not_identified",
                "candidates": [],
                "reason": "No explicit derivative identifier in input",
            }
        candidates = []
        for raw in self.products:
            identity = AssetIdentity.model_validate(raw["identity"])
            if identity.wkn not in requested:
                continue
            record = EvidenceRecord.model_validate(raw["evidence"])
            if point_in_time is None or not record.available_at(point_in_time):
                continue
            underlying_matches = decision.get("selected_wkn") == raw["underlying_wkn"]
            candidates.append(
                {
                    **identity.model_dump(mode="json"),
                    "issuer": raw["issuer"],
                    "maturity": raw["maturity"],
                    "strike": raw["strike"],
                    "ratio": raw["ratio"],
                    "underlying_wkn": raw["underlying_wkn"],
                    "underlying_matches_stock_candidate": underlying_matches,
                    "evidence": record.model_dump(mode="json"),
                    "confirmed": False,
                    "requires_official_product_document": True,
                }
            )
        return {
            "status": (
                "explicit_identifier_with_unverified_product_terms"
                if candidates
                else "unresolved_product_identifier"
            ),
            "candidates": candidates,
            "reason": (
                "Official issuer terms are still required"
                if candidates
                else "No time-valid product evidence for the explicit identifier"
            ),
        }
