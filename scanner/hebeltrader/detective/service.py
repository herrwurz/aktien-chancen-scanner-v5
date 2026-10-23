import base64
import binascii
import hashlib
import re
from datetime import UTC, datetime

from .catalog import CATALOG_REVISION, load_catalog
from .clues import extract_clues
from .ocr import TesseractOcr


def _terms(text):
    return set(re.findall(r"[a-z0-9&.]+", text.casefold()))


class DetectiveService:
    def __init__(self, *, ocr=None, catalog=None, clock=None):
        self.ocr = ocr or TesseractOcr()
        self.catalog = catalog or load_catalog()
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
        candidates = self._rank(combined, clues)
        if not candidates:
            review_hints.append("No catalog candidate has enough matching evidence")
        if request.publication_at is None:
            review_hints.append(
                "Publication timestamp missing; historical news matching is blocked"
            )
        return {
            "status": "candidate_identification_only",
            "strategy": "HEBELTRADER_DETECTIVE",
            "analyzed_at": self.clock().isoformat(),
            "publication_at": (
                request.publication_at.isoformat() if request.publication_at else None
            ),
            "catalog_revision": CATALOG_REVISION,
            "input_sources": input_sources,
            "extracted_clues": {
                key: value for key, value in clues.items() if key != "normalized_text"
            },
            "candidates": candidates[:3],
            "review_hints": review_hints,
            "identification_is_investment_recommendation": False,
            "automatic_confirmation": False,
            "observed_image_sha256": image_sha,
        }

    def _rank(self, text, clues):
        lowered = text.casefold()
        tokens = _terms(text)
        ranked = []
        for candidate in self.catalog:
            evidence = []
            score = 0
            if candidate["wkn"] in clues["wkn_fragments"]:
                score += 100
                evidence.append({"type": "exact_wkn", "value": candidate["wkn"], "weight": 100})
            if candidate["isin"] in clues["isins"]:
                score += 120
                evidence.append({"type": "exact_isin", "value": candidate["isin"], "weight": 120})
            for alias in candidate["aliases"]:
                if alias.casefold() in lowered:
                    score += 40
                    evidence.append({"type": "name_or_alias", "value": alias, "weight": 40})
            for keyword in candidate["keywords"]:
                if _terms(keyword) <= tokens:
                    score += 8
                    evidence.append({"type": "keyword", "value": keyword, "weight": 8})
            if not score:
                continue
            confidence = "high" if score >= 100 else "medium" if score >= 40 else "low"
            calls = []
            for call in candidate["calls"]:
                exact = call["wkn"] in clues["wkn_fragments"]
                calls.append(
                    call
                    | {
                        "rank_reason": "exact WKN in input"
                        if exact
                        else "linked catalog candidate",
                        "confirmed": False,
                        "requires_manual_product_verification": True,
                    }
                )
            ranked.append(
                {
                    "name": candidate["name"],
                    "ticker": candidate["ticker"],
                    "wkn": candidate["wkn"],
                    "isin": candidate["isin"],
                    "score": score,
                    "confidence": confidence,
                    "evidence": evidence,
                    "sources": candidate["sources"],
                    "call_candidates": calls,
                    "confirmed": False,
                    "missing_for_confirmation": [
                        "time-validating company/news evidence",
                        "manual identity review",
                    ],
                }
            )
        return sorted(ranked, key=lambda row: (-row["score"], row["name"]))
