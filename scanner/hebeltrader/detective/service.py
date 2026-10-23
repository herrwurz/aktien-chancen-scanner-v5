import base64
import binascii
import hashlib
import re
from datetime import UTC, datetime

from scanner.research import AssetIdentity, EvidenceRecord

from .catalog import CATALOG_REVISION, default_candidate_source, load_products
from .clues import extract_clues
from .ocr import TesseractOcr


def _phrase_present(text, phrase):
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.I) is not None


class DetectiveService:
    def __init__(
        self, *, ocr=None, candidate_source=None, news_source=None, products=None, clock=None
    ):
        self.ocr = ocr or TesseractOcr()
        self.candidate_source = candidate_source or default_candidate_source()
        self.news_source = news_source or self.candidate_source
        self.products = products if products is not None else load_products()
        self.clock = clock or (lambda: datetime.now(UTC))

    def analyze(self, request):
        text_parts = [request.teaser_text.strip(), *request.known_hints]
        input_sources = []
        review_hints = []
        if request.teaser_text.strip():
            input_sources.append({"type": "teaser_text", "characters": len(request.teaser_text)})
        image_sha = None
        if request.screenshot_base64:
            try:
                image = base64.b64decode(request.screenshot_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("invalid screenshot base64") from None
            image_sha = hashlib.sha256(image).hexdigest()
            ocr_text = self.ocr.extract(image, request.screenshot_media_type)
            text_parts.append(ocr_text)
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
        combined = "\n".join(value for value in text_parts if value)
        clues = extract_clues(combined)
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
            "status": "candidate_identification_only",
            "strategy": "HEBELTRADER_DETECTIVE",
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

    def _rank(self, text, clues, point_in_time):
        ranked = []
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
            if identity.wkn in clues["stock_wkn"]:
                hard_facts.append({"type": "exact_stock_wkn", "value": identity.wkn})
            if identity.isin in clues["isins"] and identity.isin not in clues["invalid_isins"]:
                hard_facts.append({"type": "valid_exact_stock_isin", "value": identity.isin})
            for alias in raw.get("aliases", []):
                if _phrase_present(text, alias):
                    hard_facts.append({"type": "bounded_name_or_alias", "value": alias})
            facts = {"sectors": set(), "countries": set(), "events": set()}
            for record in eligible:
                for group in facts:
                    facts[group].update(record.facts.get(group, []))
            for group in facts:
                for value in clues["structured"][group]:
                    if value in facts[group]:
                        supporting.append({"type": group, "value": value})
                    elif group == "countries" and facts[group]:
                        contradictions.append(
                            {
                                "type": "country_mismatch",
                                "value": value,
                                "candidate": sorted(facts[group]),
                            }
                        )
                for value in clues["negative"][group]:
                    if value in facts[group]:
                        contradictions.append({"type": f"negated_{group}", "value": value})
            if clues["stock_wkn"] and identity.wkn not in clues["stock_wkn"]:
                contradictions.append(
                    {"type": "different_explicit_stock_wkn", "value": clues["stock_wkn"]}
                )
            score = len(hard_facts) * 100 + len(supporting) * 12 - len(contradictions) * 30
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
            ranked.append(
                {
                    **identity.model_dump(),
                    "relevance_score_not_probability": score,
                    "evidence_strength": strength,
                    "hard_facts": hard_facts,
                    "supporting_clues": supporting,
                    "contradictions": contradictions,
                    "eligible_evidence": [record.model_dump(mode="json") for record in eligible],
                    "excluded_future_or_unavailable_source_ids": future,
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
            "reason": "strongest_supported_fixture_match_requires_manual_review",
            "selected_wkn": supported[0]["wkn"],
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
                    **identity.model_dump(),
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
