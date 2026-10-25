"""Enrich deterministic clues with search queries; optional LLM behind a flag."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from .schemas import AtomicClue, SourceSpan

SECTOR_SYNONYMS = {
    "logistics": (
        "logistik",
        "freight",
        "shipping",
        "container",
        "rail logistics",
        "schienenlogistik",
    ),
    "healthcare": ("gesundheit", "healthcare", "health", "pharma"),
    "pharma": ("pharma", "pharmaceutical", "medikamente", "gesundheit"),
    "finance": ("finanz", "bank", "finance", "wall street"),
    "retail": ("handel", "einzelhandel", "retail", "store"),
    "semiconductors": ("halbleiter", "chip", "semiconductor"),
    "energy": ("energie", "utility", "strom"),
    "insurance": ("versicherung", "insurer"),
    "sportswear": ("sportartikel", "sneaker", "apparel"),
}
EVENT_SYNONYMS = {
    "acquisition_or_stake": ("übernahme", "takeover", "acquisition", "merger"),
    "share_buyback": ("aktienrückkauf", "buyback", "share repurchase"),
    "guidance_raise": ("prognoseanhebung", "guidance raise", "raised outlook"),
    "net_income_increase": ("gewinnanstieg", "earnings growth", "steigende gewinne"),
}


class EnrichmentResult(BaseModel):
    search_queries: list[str] = Field(default_factory=list, max_length=12)
    extra_clues: list[AtomicClue] = Field(default_factory=list, max_length=40)
    notes: list[str] = Field(default_factory=list, max_length=20)
    provider: str = "heuristic"


class LlmEnrichmentPayload(BaseModel):
    """Validated LLM output: queries/synonyms only — never tickers as answers."""

    search_queries: list[str] = Field(default_factory=list, max_length=12)
    sectors: list[str] = Field(default_factory=list, max_length=12)
    countries: list[str] = Field(default_factory=list, max_length=12)
    events: list[str] = Field(default_factory=list, max_length=12)
    synonyms: list[str] = Field(default_factory=list, max_length=24)
    notes: list[str] = Field(default_factory=list, max_length=12)


class ClueEnricher(Protocol):
    def enrich(
        self, text: str, clues: list[AtomicClue], spans: list[SourceSpan]
    ) -> EnrichmentResult: ...


def _query_parts(clues: list[AtomicClue]) -> EnrichmentResult:
    queries: list[str] = []
    notes: list[str] = []
    sectors = [
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "sectors" and clue.instrument_scope == "stock"
    ]
    events = [
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "events" and clue.instrument_scope == "stock"
    ]
    facts = [
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "fact_claims" and clue.instrument_scope == "stock"
    ]
    countries = [
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "countries" and clue.instrument_scope == "stock"
    ]
    for sector in sectors:
        for synonym in SECTOR_SYNONYMS.get(sector, (sector,)):
            for event in events or ["aktie"]:
                for event_syn in EVENT_SYNONYMS.get(event, (event,)):
                    queries.append(f"{synonym} {event_syn}")
            if facts:
                queries.append(f"{synonym} {' '.join(facts[:1])}")
    # Events/facts alone are too generic for Stage-A queries (buyback/earnings noise).
    if not sectors and not countries and events:
        notes.append("events_without_sector_or_country_skipped_for_queries")
    if countries:
        queries = [f"{query} {countries[0]}" for query in queries] or [f"aktie {countries[0]}"]
    deduped = list(dict.fromkeys(item.strip() for item in queries if item.strip()))[:12]
    if not deduped:
        notes.append("no_search_queries_from_clues")
    return EnrichmentResult(search_queries=deduped, notes=notes, provider="heuristic")


class HeuristicClueEnricher:
    """Deterministic enrichment used as default and LLM fallback."""

    def enrich(
        self, text: str, clues: list[AtomicClue], spans: list[SourceSpan]
    ) -> EnrichmentResult:
        result = _query_parts(clues)
        extra: list[AtomicClue] = []
        lowered = text.casefold()
        logistics_match = re.search(r"\b(Schienen|Container)\b", text) or re.search(
            r"\b(schienen|container)\b", text, re.I
        )
        if logistics_match and not any(
            clue.value == "logistics" for clue in clues if clue.category == "sectors"
        ):
            payload = f"enrichment|logistics|{logistics_match.start()}|{logistics_match.end()}"
            extra.append(
                AtomicClue(
                    clue_id=hashlib.sha256(payload.encode()).hexdigest(),
                    category="sectors",
                    normalized="logistics",
                    quote=logistics_match.group(0),
                    source_id="enrichment:heuristic",
                    start=logistics_match.start(),
                    end=logistics_match.end(),
                    instrument_scope="stock",
                    value="logistics",
                    extraction_method="heuristic_enrichment",
                    confidence_class="medium",
                )
            )
            result.search_queries = list(
                dict.fromkeys(
                    [
                        *result.search_queries,
                        "rail logistics takeover",
                        "bahn logistik übernahme",
                        "container shipping logistics",
                    ]
                )
            )[:12]
            result.notes.append(f"inferred_logistics_from_{logistics_match.group(0).casefold()}")
        if re.search(r"\bsynerg", lowered) and "acquisition_or_stake" not in {
            clue.value for clue in clues if clue.category == "events"
        }:
            result.search_queries = list(
                dict.fromkeys([*result.search_queries, "übernahme synergien logistik"])
            )[:12]
            result.notes.append("synergy_suggests_acquisition_theme")
        return EnrichmentResult(
            search_queries=result.search_queries,
            extra_clues=extra,
            notes=result.notes,
            provider="heuristic",
        )


class HttpJsonLlmEnricher:
    """Optional HTTP JSON enricher. Never invents tickers; schema-validated only."""

    def __init__(self, endpoint: str, *, api_key: str | None = None, timeout: float = 20):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.fallback = HeuristicClueEnricher()

    def enrich(
        self, text: str, clues: list[AtomicClue], spans: list[SourceSpan]
    ) -> EnrichmentResult:
        baseline = self.fallback.enrich(text, clues, spans)
        payload = {
            "task": "hebeltrader_clue_enrichment_v1",
            "instructions": (
                "Extract sectors, countries, events, fact claims and search queries. "
                "Do not invent stock tickers, WKN, ISIN or company names as answers."
            ),
            "teaser_text": text[:8000],
            "existing_clues": [clue.model_dump(mode="json") for clue in clues[:40]],
        }
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        try:
            response = httpx.post(
                self.endpoint, headers=headers, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
            baseline.notes.append(f"llm_enrichment_failed:{type(exc).__name__}")
            return baseline
        try:
            parsed = LlmEnrichmentPayload.model_validate(body)
        except ValidationError as exc:
            baseline.notes.append(f"llm_schema_invalid:{type(exc).__name__}")
            return baseline
        # Reject payloads that try to smuggle tickers/WKN as "answers".
        banned = re.compile(r"\b(ticker|wkn|isin)\s*[:=]", re.I)
        safe_queries = [
            query.strip()
            for query in [*parsed.search_queries, *parsed.synonyms]
            if query and not banned.search(query) and len(query) <= 120
        ]
        # Prefer LLM queries while keeping heuristic coverage as fallback fill.
        merged = list(dict.fromkeys([*safe_queries, *baseline.search_queries]))[:12]
        return EnrichmentResult(
            search_queries=merged,
            extra_clues=baseline.extra_clues,
            notes=[*baseline.notes, *parsed.notes, "llm_enrichment_applied"],
            provider="llm_http_json",
        )


def build_enricher(*, endpoint: str | None = None, api_key: str | None = None) -> ClueEnricher:
    if endpoint:
        return HttpJsonLlmEnricher(endpoint, api_key=api_key)
    return HeuristicClueEnricher()
