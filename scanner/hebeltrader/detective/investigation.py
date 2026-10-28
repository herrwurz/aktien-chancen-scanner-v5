"""Primary teaser investigation: global discovery, equal comparison, falsification."""

import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from scanner.hebeltrader.eodhd import canonical, exclusive, sha
from scanner.research import AssetIdentity, EvidenceRecord

from .clue_enrichment import HeuristicClueEnricher
from .clues import extract_atomic_clues
from .research_plan import build_queries
from .retrieval import RetrievalCandidate, RetrievalReport
from .schemas import AtomicClue, DetectiveRequest
from .service import DetectiveService
from .sources import UnavailableResearchSource
from .temporal import assess_document, timestamp
from .verification import verify_candidates


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    teaser_text: str = Field(default="", max_length=20000)
    teaser_url: HttpUrl | None = None
    original_source_url: HttpUrl | None = None
    source_retrieved_at: datetime | None = None
    headline: str = Field(default="", max_length=500)
    publisher: str = Field(default="", max_length=200)
    author: str = Field(default="", max_length=200)
    issue: str = Field(default="", max_length=100)
    evaluation_class: str = Field(
        default="unclassified",
        pattern="^(unclassified|development_regression|retrospective|prospective_blind)$",
    )
    previously_used_for_development: bool | None = None
    publication_at: datetime | None = None
    publication_date: date | None = None
    advertised_return: str | None = Field(default=None, max_length=100)
    screenshot_base64: str | None = Field(default=None, max_length=3000000)
    screenshot_media_type: str | None = None
    pdf_base64: str | None = Field(default=None, max_length=28000000)
    pdf_media_type: str | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.source_retrieved_at and self.source_retrieved_at.utcoffset() is None:
            raise ValueError("source retrieval timestamp timezone required")
        if self.publication_at and self.publication_at.utcoffset() is None:
            raise ValueError("publication timestamp timezone required")
        if not any(
            (self.teaser_text.strip(), self.teaser_url, self.screenshot_base64, self.pdf_base64)
        ):
            raise ValueError("text, public URL, screenshot or PDF required")
        return self


def _entities(text):
    # Company/partner names are taken only from the actual input, never case history.
    found = re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9]*\b", text)
    found += re.findall(
        r"\b[A-Z][A-Za-z0-9&-]+\s+(?:Semiconductor|Technologies|Therapeutics|Systems|Corporation)\b",
        text,
    )
    found += re.findall(
        r"\b(?:von|mit|an|acquires?|acquired|partners? with)\s+"
        r"([A-Z][A-Za-z0-9&-]+(?:\s+[A-Z][A-Za-z0-9&-]+){0,2})",
        text,
    )
    return list(dict.fromkeys(value.strip() for value in found))[:12]


_RELATIONS = {
    "acquisition": r"übernah\w*|zukäuf\w*|acquir\w*|acquisition|merger|erwarb",
    "investment": r"invest\w*|beteilig\w*|minority stake",
    "partnership": r"partner\w*|kooper\w*|collaborat\w*",
}


def _relation(text, start):
    candidates = []
    for kind, pattern in _RELATIONS.items():
        for match in re.finditer(r"\b(?:" + pattern + r")\b", text, re.I):
            if match.start() <= start and start - match.end() <= 160:
                candidates.append((match.end(), kind))
    return max(candidates)[1] if candidates else "unknown_relation"


def _clues(text, spans):
    clues = extract_atomic_clues(text, spans)
    for name in _entities(text):
        start = text.index(name)
        relation = _relation(text, start)
        target = relation + "|" + name.casefold()
        clues.append(
            AtomicClue(
                clue_id=sha(target.encode()),
                category="fact_claims",
                normalized=target,
                value=target,
                quote=name,
                source_id="teaser_text",
                start=start,
                end=start + len(name),
                instrument_scope="stock",
                extraction_method="named_entity_literal_requires_transaction_context",
            )
        )
    quarters = set(re.findall(r"\bQ[1-4]\s+20\d{2}\b", text, re.I))
    period = next(iter(quarters)).upper() if len(quarters) == 1 else None
    normalized = []
    for clue in clues:
        if clue.category == "financial_metric":
            clue = clue.model_copy(update={"period": period})
        normalized.append(clue)
    # Overlapping regex matches and repeated wording are not independent evidence.
    return list(
        {
            (c.category, c.normalized, c.value, c.unit, c.period, c.polarity): c for c in normalized
        }.values()
    )


def _queries(text, clues, spans):
    enrichment = HeuristicClueEnricher().enrich(text, clues, spans)
    return build_queries(text, _entities(text), enrichment.search_queries)


def _evidence(document, clues, cutoff):
    timing = assess_document(document, cutoff)
    text = document.get("text", "")
    facts = {
        "origin_id": document["url"],
        "fact_claims": [],
        "support_quotes": {},
        "financial_metrics": [],
        "contradicted_fact_claims": [],
        "teaser_term_overlap": sorted(
            {
                (c.value or c.normalized).split("|")[-1]
                for c in clues
                if c.instrument_scope == "stock"
                and c.category in {"fact_claims", "financial_metric", "sectors", "business"}
                and re.search(
                    r"(?<!\w)" + re.escape((c.value or c.normalized).split("|")[-1]) + r"(?!\w)",
                    text,
                    re.I,
                )
            }
        ),
    }
    for clue in clues:
        if clue.category == "fact_claims":
            value = clue.value or clue.normalized
            relation, separator, term = value.partition("|")
            if not separator or relation not in _RELATIONS:
                continue
            match = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)
            if not match:
                continue
            context = text[max(0, match.start() - 100) : match.end() + 100]
            pattern = _RELATIONS[relation]
            company = document.get("company_name", "")
            subject = (
                re.search(
                    re.escape(company)
                    + r"(?P<link>[^.!?]{0,120})\b(?:"
                    + pattern
                    + r")\b[^.!?]{0,80}"
                    + re.escape(term),
                    context,
                    re.I,
                )
                if company
                else None
            )
            if subject and not re.search(
                r"\b(?:competitor|konkurrent|according|says|said)\b", subject.group("link"), re.I
            ):
                denial = re.search(
                    r"\b(?:not|never|nicht|keine?)\b.{0,35}\b(?:" + pattern + r")\b", context, re.I
                )
                facts["contradicted_fact_claims" if denial else "fact_claims"].append(value)
                facts["support_quotes"][clue.clue_id] = context
        elif clue.category == "financial_metric":
            for observed in _clues(text, []):
                prefix = re.split(r"[.!?;\n]", text[: observed.start])[-1]
                subject_matches = bool(
                    document.get("company_name")
                    and re.search(
                        r"(?<!\w)"
                        + re.escape(document["company_name"])
                        + r"(?:\s+(?:reported|reports|meldet|meldete|verzeichnet|"
                        r"verzeichnete|erzielt|erzielte)){0,1}\s*[:,–-]?\s*$",
                        prefix,
                        re.I,
                    )
                )
                if (
                    subject_matches
                    and observed.category == "financial_metric"
                    and clue.period
                    and observed.period == clue.period
                ):
                    facts["financial_metrics"].append(
                        {
                            "metric": observed.normalized,
                            "unit": observed.unit,
                            "value": observed.value,
                        }
                    )
    if not timing["published_at"] or not timing["retrieved_at"]:
        return None
    published = datetime.fromisoformat(timing["published_at"])
    kind = document.get("source_kind", "unknown")
    kind = kind if kind in {"issuer", "regulatory", "product_document"} else "news"
    return EvidenceRecord(
        source_id=sha(document["url"].encode()),
        url=document["url"],
        title=document.get("title", ""),
        published_at=published,
        effective_at=datetime.fromisoformat(timing["event_at"])
        if timing["event_at"]
        else published,
        source_available_at=(
            datetime.fromisoformat(timing["source_available_at"])
            if timing["eligibility"] == "eligible"
            else None
        ),
        retrieved_at=datetime.fromisoformat(document["retrieved_at"].replace("Z", "+00:00")),
        source_kind=kind,
        facts=facts,
        content_sha256=document.get("raw_sha256") or sha(text.encode()),
    )


class Investigator:
    def __init__(self, root, *, web=None, clock=None, product_issuers=None):
        self.root = Path(root)
        self.web = web
        self.product_issuers = product_issuers or {}
        self.clock = clock or (lambda: datetime.now(UTC))

    def analyze(self, request, *, documents=None, historical_blind=False, case_id=None):
        if historical_blind and (
            documents is None or self.web is not None or request.publication_at is None
        ):
            raise ValueError(
                "historical blind requires archived packet, publication time and no live search"
            )
        started = perf_counter()
        run_id = uuid.uuid4().hex
        folder = self.root / "analyses" / run_id
        retrieved = self.clock()
        errors = []
        publication_basis = "operator_supplied" if request.publication_at else "unknown"
        source_text = "\n".join(part for part in (request.headline, request.teaser_text) if part)
        if request.teaser_url:
            if self.web is None:
                raise ValueError("public web access not configured for URL input")
            original = self.web.fetch(str(request.teaser_url))
            source_text += "\n" + original["text"]
            if request.publication_at is None and original.get("published_at"):
                request = request.model_copy(
                    update={
                        "publication_at": datetime.fromisoformat(
                            original["published_at"].replace("Z", "+00:00")
                        )
                    }
                )
                publication_basis = "original_page_metadata"
            exclusive(folder / "original-source.json", canonical(original))
        input_truncated = len(source_text) > 20000
        original = DetectiveRequest(
            teaser_text=source_text[:20000],
            screenshot_base64=request.screenshot_base64,
            screenshot_media_type=request.screenshot_media_type,
            pdf_base64=request.pdf_base64,
            pdf_media_type=request.pdf_media_type,
            publication_at=request.publication_at,
        )
        text, spans, input_sources, notes, image_sha = DetectiveService(
            candidate_source=UnavailableResearchSource("input_extraction_only"), products=[]
        ).extract_inputs(original)
        input_truncated = input_truncated or len(text) > 20000
        text = text[:20000]
        exclusive(folder / "input.json", canonical(request.model_dump(mode="json")))
        exclusive(folder / "extracted.txt", text.encode())
        clues = _clues(text, spans)
        queries = _queries(text, clues, spans)
        fetched = list(documents or [])
        offline = documents is not None or self.web is None

        def research(query):
            try:
                for hit in self.web.search(query, limit=10):
                    if any(doc["url"] == hit["url"] for doc in fetched):
                        continue
                    try:
                        fetched.append(self.web.fetch(hit["url"]))
                    except (ValueError, httpx.HTTPError) as exc:
                        errors.append({"url": hit["url"], "error": str(exc)[:120]})
            except (ValueError, httpx.HTTPError) as exc:
                errors.append({"query": query, "error": str(exc)[:120]})

        if not offline:
            for query in queries:
                research(query)

        cutoff = request.publication_at or retrieved

        def compare():
            groups = {}
            for doc in fetched:
                if (
                    timestamp(doc.get("published_at"))
                    and timestamp(doc.get("published_at")) > cutoff
                ):
                    continue
                if historical_blind and assess_document(doc, cutoff)["eligibility"] != "eligible":
                    continue
                name = doc.get("company_name")
                if not name:
                    continue
                canonical_name = re.sub(
                    r"\b(?:incorporated|inc|corporation|corp|limited|ltd|plc|ag)\b",
                    "",
                    name.casefold(),
                )
                canonical_name = " ".join(re.findall(r"\w+", canonical_name))
                asset_id = "company:" + hashlib.sha256(canonical_name.encode()).hexdigest()
                group = groups.setdefault(
                    asset_id, {"name": name, "ticker": doc.get("ticker"), "records": []}
                )
                record = _evidence(doc, clues, cutoff)
                if record:
                    group["records"].append(record)
            identities = {
                asset_id: AssetIdentity(
                    asset_type="stock",
                    name=row["name"],
                    ticker=row["ticker"],
                    source_id="public_company_document",
                    retrieved_at=retrieved,
                    instrument_type_status="unknown",
                    quality_status="candidate",
                )
                for asset_id, row in groups.items()
            }
            # Reuse the existing Stage-B checker. No invented identity cards or case-label facts.
            hits = [
                RetrievalCandidate(
                    asset_id=asset_id,
                    identity=identity,
                    rrf_score=0,
                    structured_score=0,
                    total_score=0,
                    channel_ranks={},
                    uncertainties=[],
                )
                for asset_id, identity in identities.items()
            ]
            retrieval = RetrievalReport(
                status="ok",
                candidates=hits,
                full_universe_size=len(hits),
                visible_universe_size=len(hits),
                matched_before_limit=len(hits),
                channel_limit=50,
                channel_counts={"global_public_documents": len(hits)},
                channel_matched_before_limit={},
            )
            rows = verify_candidates(
                retrieval,
                clues,
                lambda identity: next(
                    group["records"] for group in groups.values() if group["name"] == identity.name
                ),
                cutoff,
            )
            by_clue = {c.clue_id: c for c in clues}
            result = []
            for row in rows:
                primary_ids = {
                    cluster.cluster_id for cluster in row.evidence_clusters if cluster.primary
                }
                specific = [
                    cell.clue_id
                    for cell in row.evidence_matrix
                    if cell.status == "confirmed"
                    and by_clue[cell.clue_id].category in {"fact_claims", "financial_metric"}
                    and bool(primary_ids.intersection(cell.evidence_cluster_ids))
                ]
                score = sum(50 if by_clue[c].category == "fact_claims" else 35 for c in specific)
                score += min(10, row.evidence_score // 10)
                score -= 100 * len(row.hard_contradictions)
                result.append(
                    {
                        "asset_id": row.asset_id,
                        "identity": row.identity,
                        "evidence_score": score,
                        "evidence_matrix": [
                            cell.model_dump()
                            | {
                                "quote": by_clue[cell.clue_id].quote,
                                "category": by_clue[cell.clue_id].category,
                            }
                            for cell in row.evidence_matrix
                        ],
                        "confirmed_specific_clues": specific,
                        "hard_contradictions": row.hard_contradictions,
                        "unknown_clues": row.unknown_clue_ids,
                        "sources": row.eligible_evidence,
                        "comparison_evidence_available": any(
                            record.get("facts", {}).get("teaser_term_overlap")
                            for record in row.eligible_evidence
                        ),
                        "counterarguments": row.hard_contradictions
                        or ["Unbestätigte Hinweise in der Matrix prüfen."],
                    }
                )
            result.sort(
                key=lambda row: (
                    bool(row["hard_contradictions"]),
                    -row["evidence_score"],
                    row["asset_id"],
                )
            )
            return result

        ranked = compare()
        peer_comparison = {
            "status": "not_performed_offline" if offline else "not_performed_no_candidates",
            "queries": [],
            "initial_candidates": len(ranked),
        }
        if not offline and ranked:
            peer_queries = [
                f'"{row["identity"]["name"]}" competitors peer group annual report'
                for row in ranked[:3]
            ]
            previous_errors = len(errors)
            for query in peer_queries:
                research(query)
            ranked = compare()
            peer_comparison.update(
                status="searched_with_source_gaps" if len(errors) > previous_errors else "searched",
                queries=peer_queries,
            )
        peer_comparison["candidates_after_discovery"] = len(ranked)
        falsification = {
            "status": "not_performed_offline",
            "queries": [],
            "leader_before": ranked[0]["asset_id"] if ranked else None,
        }
        if not offline and ranked:
            falsification["top3_before"] = [r["asset_id"] for r in ranked[:3]]
            falsification_queries = [
                f'"{row["identity"]["name"]}" '
                + " ".join(_entities(text)[:2])
                + " denied cancelled acquisition earnings guidance competitor"
                for row in ranked[:3]
            ]
            for query in falsification_queries:
                research(query)
            falsification.update(
                status="performed" if not errors else "performed_with_source_gaps",
                queries=falsification_queries,
            )
            ranked = compare()
        counter_count = max(
            0,
            sum(row["comparison_evidence_available"] for row in ranked)
            - int(bool(ranked and ranked[0]["comparison_evidence_available"])),
        )
        limits = []
        if input_truncated:
            limits.append("input_excerpt_truncated")
        if counter_count < 5:
            limits.append("fewer_than_five_countercandidates")
        if not request.publication_at:
            limits.append("teaser_publication_time_unknown")
        if offline:
            limits.append("active_falsification_not_performed")
        if errors:
            limits.append("research_source_gaps")
        if not ranked or len(ranked[0]["confirmed_specific_clues"]) < 2:
            limits.append("insufficient_specific_primary_evidence")
        if ranked and not ranked[0]["identity"].get("ticker"):
            limits.append("listed_underlying_identity_unverified")
        if len(ranked) > 1 and ranked[0]["evidence_score"] - ranked[1]["evidence_score"] < 35:
            limits.append("ambiguous_leading_candidates")
        if ranked and falsification.get("leader_before") != ranked[0]["asset_id"]:
            limits.append("new_leader_needs_falsification")
        checked_top3 = set(falsification.get("top3_before", []))
        if not offline and any(r["asset_id"] not in checked_top3 for r in ranked[:3]):
            limits.append("new_top3_candidate_needs_falsification")
        if request.publication_at and request.publication_at > retrieved:
            limits.append("future_teaser_publication")
        identified = bool(
            not limits
            and ranked
            and counter_count >= 5
            and len(ranked[0]["confirmed_specific_clues"]) >= 2
            and not ranked[0]["hard_contradictions"]
            and request.publication_at
            and not offline
            and not errors
            and (len(ranked) < 2 or ranked[0]["evidence_score"] - ranked[1]["evidence_score"] >= 35)
        )
        report = {
            "schema_version": 4,
            "case_id": case_id or run_id,
            "strategy": "HEBELTRADER_DETECTIVE",
            "run_id": run_id,
            "analyzed_at": self.clock().isoformat(),
            "teaser_sha256": sha(text.encode()),
            "publication_at": request.publication_at.isoformat()
            if request.publication_at
            else None,
            "publication_time_basis": publication_basis,
            "publication_date": request.publication_date.isoformat()
            if request.publication_date
            else None,
            "original_source_url": str(request.original_source_url or request.teaser_url)
            if (request.original_source_url or request.teaser_url)
            else None,
            "source_retrieved_at": request.source_retrieved_at.isoformat()
            if request.source_retrieved_at
            else None,
            "headline": request.headline,
            "publisher": request.publisher,
            "author": request.author,
            "issue": request.issue,
            "advertised_return": request.advertised_return
            or next((c.value for c in clues if c.instrument_scope == "promotional"), None),
            "identification": {
                "status": "identified" if identified else "not_identified",
                "label": "Identifiziert, manuell prüfen" if identified else "Nicht identifiziert",
                "score_is_probability": False,
                "requires_manual_review": True,
            },
            "candidates": ranked[:3],
            "checked_candidates": ranked,
            "countercandidate_count": counter_count,
            "criteria": [clue.model_dump(mode="json") for clue in clues],
            "source_timing": [assess_document(doc, cutoff) for doc in fetched],
            "falsification": falsification,
            "peer_comparison": peer_comparison,
            "search_queries": queries,
            "limitations": limits,
            "research_errors": errors,
            "discovery_source_gaps": getattr(self.web, "discovery_errors", []),
            "configured_discovery_feeds": getattr(self.web, "discovery_feeds", []),
            "source_quality": {
                "primary_documents": sum(
                    d.get("source_kind") in {"issuer", "regulatory"} for d in fetched
                ),
                "documents": len(fetched),
                "scope": "global_public_search_not_complete_world_market",
            },
            "analysis_seconds": round(perf_counter() - started, 3),
            "historical_blind_eligible": bool(historical_blind),
            "research_mode": "operator_packet"
            if documents is not None
            else "public_web"
            if self.web
            else "offline",
            "derivative_candidate": {
                "status": "not_identified",
                "reason": "official_product_evidence_required_after_stock_identification",
            },
            "automatic_confirmation": False,
            "identification_is_investment_recommendation": False,
            "input_sources": input_sources,
            "review_hints": notes,
            "observed_image_sha256": image_sha,
        }
        report["decision"] = {
            "status": "likely_identified"
            if identified
            else "plausible_hypothesis"
            if ranked and any(r["confirmed_specific_clues"] for r in ranked[:3])
            else "insufficient_evidence",
            "label": "Wahrscheinlich identifiziert"
            if identified
            else "Plausible Hypothese"
            if ranked and any(r["confirmed_specific_clues"] for r in ranked[:3])
            else "Nicht ausreichend identifizierbar",
        }
        for rank, row in enumerate(report["candidates"], 1):
            row["ranking_reason"] = (
                f"Rang {rank}: {len(row['confirmed_specific_clues'])} bestätigte Kernhinweise, "
                f"{len(row['hard_contradictions'])} harte Widersprüche, "
                f"Score {row['evidence_score']}; "
                "Widersprüche zuerst, danach spezifische Primärevidenz."
            )
        from .product_research import research_calls

        report["derivative_candidate"] = research_calls(
            report, self.web, self.product_issuers, text
        )
        exclusive(folder / "sources.json", canonical(fetched))
        from .history import freeze_analysis

        freeze_analysis(report, folder / "ranking.json")
        report["artifact_directory"] = str(folder)
        return report
