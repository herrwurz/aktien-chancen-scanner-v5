"""Primary teaser investigation: global discovery, equal comparison, falsification."""

import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from itertools import zip_longest
from pathlib import Path
from time import perf_counter

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from scanner.hebeltrader.eodhd import canonical, exclusive, sha
from scanner.research import AssetIdentity, EvidenceRecord

from .chart_check import chart_score
from .chart_check import check as chart_check
from .clue_enrichment import HeuristicClueEnricher
from .clues import extract_atomic_clues
from .research_plan import build_queries
from .retrieval import RetrievalCandidate, RetrievalReport
from .schemas import AtomicClue, DetectiveRequest
from .service import DetectiveService
from .sources import UnavailableResearchSource
from .structure_screen import screen_queries, screened_names, structure_bonus, ticker_for
from .temporal import assess_document, timestamp
from .verification import verify_candidates


def clue_specificity(text):
    value = str(text or "").casefold()
    if re.search(
        r"kaum (?:noch )?eine wahl|keine alternative|einzig(?:e|er|es)|"
        r"monopol|unverzichtbar|exclusive|only commercially|sole supplier",
        value,
    ):
        return 12
    if re.search(r"übernahm|übernahme|acquisition|großauftrag|partnerschaft|zulassung", value):
        return 8
    if re.search(r"bruttomarge|cashflow|umsatz|gewinn|marge|revenue|earnings", value):
        return 3
    if re.search(r"chart|kursziel|rendite|ausbruch|rally", value):
        return 0
    return 2


def apply_tie_labels(ranked):
    tied = bool(len(ranked) > 1 and ranked[0]["evidence_score"] == ranked[1]["evidence_score"])
    if tied:
        for row in ranked:
            if row["evidence_score"] == ranked[0]["evidence_score"]:
                row["rank_label"] = "Gleichstand Rang 1"
    return tied


def source_class(document):
    explicit = document.get("source_class")
    if explicit in {"A", "B", "C", "D"}:
        return explicit
    return {
        "issuer": "A",
        "regulatory": "A",
        "product_document": "A",
        "tavily_extract": "B",
        "search_snippet": "C",
    }.get(document.get("source_kind"), "D")


def finding_timing(document, cutoff, *, current_hypothesis):
    assessment = assess_document(document, cutoff)
    if assessment["eligibility"] == "eligible":
        return {"temporal_eligibility": "eligible", "usable_for_ranking": True}
    if (
        current_hypothesis
        and assessment["eligibility"] == "uncertain"
        and source_class(document) in {"A", "B", "C", "D"}
        and timestamp(document.get("retrieved_at"))
        and timestamp(document.get("retrieved_at")) <= cutoff
    ):
        return {
            "temporal_eligibility": "current_hypothesis_only",
            "usable_for_ranking": True,
        }
    return {
        "temporal_eligibility": assessment["eligibility"],
        "usable_for_ranking": False,
    }


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
    # German capitalizes every noun, so a bare noun after "mit/von/an" is only a candidate
    # entity when a transaction word precedes it.
    for match in re.finditer(
        r"\b(?:von|mit|an|acquires?|acquired|partners? with)\s+"
        r"([A-Z][A-Za-z0-9&-]+(?:\s+[A-Z][A-Za-z0-9&-]+){0,2})",
        text,
    ):
        if _relation(text, match.start(1)) != "unknown_relation" or " " in match.group(1):
            found.append(match.group(1))
    return list(dict.fromkeys(value.strip() for value in found))[:12]


SEARCH_LOGIC_VERSION = "2026-10-31-search-v8"
_LEGAL_WORDS = re.compile(
    r"\b(?:incorporated|inc|corporation|corp|limited|ltd|plc|ag|se|sa|nv|n v|holding|holdings"
    r"|co|company|group|the)\b"
)
_ALIASES = {
    "tsmc": "taiwan semiconductor manufacturing",
    "tsm": "taiwan semiconductor manufacturing",
}


def canonical_company(name, ticker=None):
    """Merge legal-form, parenthetical and ticker variants of one issuer name."""
    text = re.sub(r"\([^)]*\)", " ", str(name).casefold()).replace(".", "")
    text = " ".join(re.findall(r"\w+", _LEGAL_WORDS.sub(" ", text)))
    return _ALIASES.get(text, text)


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


def _is_hypothesis(name, hypotheses):
    # A document about a shortlisted company stays comparison evidence even without AI-cited
    # clue support; the ranking then relies on structure and chart instead.
    key = canonical_company(name)
    return any(canonical_company(h) == key for h in hypotheses)


def _apply_chart(ranked, cache, text, top=6):
    # Chart clues (long uptrend, breakout) are checked with market data, not web text.
    for row in ranked:
        data = row["identity"]
        data = data if isinstance(data, dict) else data.model_dump()
        structure = structure_bonus(data.get("name") or "", text)
        if structure:
            row["market_structure"] = structure
            row["evidence_score"] += structure["bonus"]
    for row in ranked[:top]:
        identity = row["identity"]
        data = identity if isinstance(identity, dict) else identity.model_dump()
        ticker = data.get("ticker") or ticker_for(data.get("name") or "")
        key = row["asset_id"]
        if key not in cache:
            cache[key] = chart_check(ticker) if ticker else {"status": "no_ticker"}
        result = cache[key]
        row["chart"] = result
        if result["status"] == "ok":
            row["evidence_score"] += chart_score(result)
    ranked.sort(
        key=lambda row: (bool(row["hard_contradictions"]), -row["evidence_score"], row["asset_id"])
    )


def _interleave(planned, screened, fallback, cap=10):
    # Alternate AI-planned and structure-screened queries so the shared request budget
    # reaches every value-chain layer instead of being spent on the first few queries.
    merged = []
    for pair in zip_longest(planned[:5], screened[:5]):
        merged.extend(q for q in pair if q)
    return list(dict.fromkeys(merged + planned[5:] + fallback))[:cap]


def _queries(text, clues, spans):
    enrichment = HeuristicClueEnricher().enrich(text, clues, spans)
    return build_queries(text, _entities(text), enrichment.search_queries)


def _evidence(document, clues, cutoff, *, allow_undated=False):
    undated = allow_undated and not document.get("published_at") and document.get("retrieved_at")
    if undated:
        # Live hypothesis mode: undated issuer pages are provisional evidence dated at retrieval.
        document = dict(document, published_at=document["retrieved_at"])
    timing = assess_document(document, cutoff)
    text = document.get("text", "")
    facts = {
        "origin_id": document["url"],
        "fact_claims": [],
        "support_quotes": {},
        "financial_metrics": [],
        "contradicted_fact_claims": [],
        "published_at_assumed_retrieval": bool(undated),
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
        semantic_clues = []
        hypotheses = []
        apis = getattr(self.web, "apis", None)
        if not offline and apis is not None and apis.ai_key:
            try:
                planned = apis.plan(text)
                semantic_clues = planned["clues"]
                hypotheses = list(
                    dict.fromkeys(planned.get("candidate_hypotheses", []) + screened_names(text))
                )
                for item in semantic_clues:
                    start = text.index(item["quote"])
                    clues.append(
                        AtomicClue(
                            clue_id=item["clue_id"],
                            category="semantic_fact",
                            normalized=item["description"],
                            value=item["description"],
                            quote=item["quote"],
                            start=start,
                            end=start + len(item["quote"]),
                            source_id="teaser_text",
                            instrument_scope="stock",
                            extraction_method="ai_literal_quote_requires_manual_review",
                        )
                    )
                queries = _interleave(planned["queries"], screen_queries(text), queries)
            except (ValueError, httpx.HTTPError) as exc:
                errors.append({"source": "ai_planner", "error": str(exc)[:120]})

        set_phase = getattr(self.web, "set_phase", lambda phase: None)
        set_phase("discovery")

        def research(query):
            loaded = 0
            try:
                hits = [
                    hit
                    for hit in self.web.search(query, limit=10)
                    if not any(doc["url"] == hit["url"] for doc in fetched)
                ]
                fetch_many = getattr(self.web, "fetch_many", None)
                if fetch_many:
                    limit = (
                        (2 if len(queries) > 8 else 3)
                        if getattr(self.web, "phase", None) == "discovery"
                        else len(hits)
                    )
                    documents_batch, batch_errors = fetch_many([hit["url"] for hit in hits[:limit]])
                    fetched.extend(documents_batch)
                    errors.extend(batch_errors)
                    # Remaining search hits keep their provider snippet instead of being dropped.
                    snippet = getattr(self.web, "snippet_document", None)
                    seen = {doc["url"] for doc in fetched}
                    for hit in hits[limit : limit + 5] if snippet else []:
                        if hit["url"] not in seen and hit.get("content"):
                            fetched.append(snippet(hit["url"]))
                    return
                for hit in hits:
                    if not getattr(self.web, "can_fetch_new_document", lambda: True)():
                        break
                    try:
                        fetched.append(self.web.fetch(hit["url"]))
                        loaded += 1
                        # Spread initial API discovery across different clue queries.
                        if getattr(self.web, "phase", None) == "discovery" and loaded >= 3:
                            break
                    except (ValueError, httpx.HTTPError) as exc:
                        errors.append({"url": hit["url"], "error": str(exc)[:120]})
            except (ValueError, httpx.HTTPError) as exc:
                errors.append({"query": query, "error": str(exc)[:120]})

        if not offline:
            for query in queries:
                research(query)

        cutoff = request.publication_at or retrieved

        def compare():
            nonlocal cutoff
            if request.publication_at is None:
                cutoff = self.clock()
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
                if not name and hypotheses:
                    haystack = doc.get("title", "") + "\n" + doc.get("text", "")[:8000]
                    name = next(
                        (
                            h
                            for h in hypotheses
                            if re.search(r"(?<!\w)" + re.escape(h) + r"(?!\w)", haystack, re.I)
                        ),
                        None,
                    )
                    if name:
                        doc = dict(
                            doc, company_name=name, identity_basis="hypothesis_literal_mention"
                        )
                if not name:
                    continue
                interpretation = doc.get("ai_interpretation")
                if (
                    isinstance(interpretation, dict)
                    and not interpretation.get("ticker")
                    and not interpretation.get("findings")
                    and not _is_hypothesis(name, hypotheses)
                ):
                    # A named publisher, research platform, or article author is not enough to
                    # establish a listed-stock candidate. Keep only identities tied to a quoted
                    # teaser clue or an explicitly quoted ticker.
                    continue
                canonical_name = canonical_company(name, doc.get("ticker"))
                asset_id = "company:" + hashlib.sha256(canonical_name.encode()).hexdigest()
                group = groups.setdefault(
                    asset_id,
                    {"name": name, "ticker": doc.get("ticker"), "records": [], "documents": []},
                )
                group["documents"].append(doc)
                record = _evidence(doc, clues, cutoff, allow_undated=request.publication_at is None)
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
                cited = []
                if not offline and apis is not None:
                    from .external_research import validate_interpretation

                    for doc in groups[row.asset_id]["documents"]:
                        interpretation = validate_interpretation(
                            doc, semantic_clues, doc.get("ai_interpretation", {})
                        )
                        if interpretation:
                            for finding in interpretation["findings"]:
                                timing = finding_timing(
                                    doc,
                                    cutoff,
                                    current_hypothesis=request.publication_at is None,
                                )
                                cited.append(
                                    dict(
                                        finding,
                                        url=doc["url"],
                                        source_kind=doc.get("source_kind"),
                                        source_class=source_class(doc),
                                        published_at=doc.get("published_at"),
                                        retrieved_at=doc.get("retrieved_at"),
                                        **timing,
                                        verification="ai_interpretation_requires_manual_review",
                                    )
                                )
                supported = {
                    c["clue_id"]
                    for c in cited
                    if c["status"] == "supported" and c["usable_for_ranking"]
                }
                disputed = {
                    c["clue_id"]
                    for c in cited
                    if c["status"] == "contradicted" and c["usable_for_ranking"]
                }
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
                score += sum(
                    clue_specificity(by_clue[clue_id].quote)
                    for clue_id in supported - disputed
                    if clue_id in by_clue
                )
                score -= sum(
                    clue_specificity(by_clue[clue_id].quote)
                    for clue_id in disputed
                    if clue_id in by_clue
                )
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
                        "cited_findings": cited,
                        "hard_contradictions": row.hard_contradictions,
                        "unknown_clues": row.unknown_clue_ids,
                        "sources": row.eligible_evidence,
                        "comparison_evidence_available": any(c["usable_for_ranking"] for c in cited)
                        or any(
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
        chart_cache = {}
        if not offline:
            _apply_chart(ranked, chart_cache, text)
        set_phase("peers")
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
        set_phase("falsification")
        falsification = {
            "status": "not_performed_offline" if offline else "not_performed_no_candidates",
            "queries": [],
            "leader_before": ranked[0]["asset_id"] if ranked else None,
        }
        if not offline and ranked:
            falsification["top3_before"] = [r["asset_id"] for r in ranked[:3]]
            falsification_queries = [
                " ".join(
                    [
                        f'"{row["identity"]["name"]}"',
                        *_entities(text)[:2],
                        "denied cancelled acquisition earnings guidance competitor",
                    ]
                )
                for row in ranked[:3]
            ]
            for query in falsification_queries:
                research(query)
            falsification.update(
                status="performed" if not errors else "performed_with_source_gaps",
                queries=falsification_queries,
            )
            ranked = compare()
        if not offline:
            _apply_chart(ranked, chart_cache, text)
        reasoning_review = {
            "status": "not_available_offline" if offline else "not_performed_no_candidates",
            "changes_deterministic_ranking": False,
        }
        if not offline and apis is not None and apis.ai_key and ranked:
            try:
                reasoning_review = apis.review_candidates(ranked[:3])
            except (ValueError, httpx.HTTPError) as exc:
                reasoning_review = {
                    "status": "failed",
                    "error": str(exc)[:120],
                    "changes_deterministic_ranking": False,
                }
                errors.append({"source": "reasoning_review", "error": str(exc)[:120]})
        top_tie = apply_tie_labels(ranked)
        counter_count = max(
            0,
            sum(row["comparison_evidence_available"] for row in ranked)
            - int(bool(ranked and ranked[0]["comparison_evidence_available"])),
        )
        limits = []
        if semantic_clues or any(doc.get("ai_interpretation") for doc in fetched):
            limits.append("ai_interpretation_requires_manual_verification")
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
        if ranked and any(
            c["status"] == "contradicted" and c["usable_for_ranking"]
            for c in ranked[0]["cited_findings"]
        ):
            limits.append("ai_counterevidence_requires_review")
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
            "knowledge_as_of": cutoff.isoformat(),
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
            "ranking_tie": top_tie,
            "ranking_status": "ambiguous_tie" if top_tie else "ranked",
            "criteria": [clue.model_dump(mode="json") for clue in clues],
            "semantic_research": {
                "enabled": bool(apis and apis.ai_key and not offline),
                "validated_teaser_clues": len(semantic_clues),
                "search_api_calls": getattr(apis, "search_calls", 0),
                "ai_api_calls": getattr(apis, "ai_calls", 0),
                "models": {
                    "extraction": getattr(apis, "extraction_model", None),
                    "reasoning": getattr(apis, "reasoning_model", None),
                },
                "calls_by_model": getattr(apis, "calls_by_model", {}),
                "usage": getattr(apis, "usage_summary", lambda: None)(),
                "findings_are_provisional": True,
                "budget": apis.budget.summary() if apis is not None else None,
            },
            "source_timing": [assess_document(doc, cutoff) for doc in fetched],
            "researched_sources": [
                {
                    "url": doc.get("url"),
                    "title": doc.get("title", ""),
                    "source_class": source_class(doc),
                    "source_kind": doc.get("source_kind"),
                    "raw_sha256": doc.get("raw_sha256"),
                    "retrieved_at": doc.get("retrieved_at"),
                    "published_at": doc.get("published_at"),
                    "provider_score": doc.get("provider_score"),
                    "text_excerpt": str(doc.get("text", ""))[:500],
                }
                for doc in fetched
            ],
            "falsification": falsification,
            "reasoning_review": reasoning_review,
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
            "search_logic_version": SEARCH_LOGIC_VERSION,
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
        source_errors = errors + list(getattr(self.web, "discovery_errors", []))
        report["research_diagnostics"] = {
            "documents": len(fetched),
            "documents_with_company_identity": sum(bool(d.get("company_name")) for d in fetched),
            "request_attempts": len(getattr(self.web, "attempts", [])),
            "requests_remaining": getattr(self.web, "remaining", None),
            "source_errors": source_errors,
        }
        source_blocked = not offline and not ranked and bool(source_errors)
        report["decision"] = {
            "status": "ambiguous_tie"
            if top_tie and ranked
            else "research_unavailable"
            if source_blocked
            else "likely_identified"
            if identified
            else "plausible_hypothesis"
            if ranked
            and any(
                r["confirmed_specific_clues"]
                or any(
                    c["status"] == "supported" and c["usable_for_ranking"]
                    for c in r["cited_findings"]
                )
                for r in ranked[:3]
            )
            else "insufficient_evidence",
            "label": "Keine eindeutige Rangfolge"
            if top_tie and ranked
            else "Recherche derzeit nicht verfügbar"
            if source_blocked
            else "Wahrscheinlich identifiziert"
            if identified
            else "Plausible Hypothese"
            if ranked
            and any(
                r["confirmed_specific_clues"]
                or any(
                    c["status"] == "supported" and c["usable_for_ranking"]
                    for c in r["cited_findings"]
                )
                for r in ranked[:3]
            )
            else "Nicht ausreichend identifizierbar",
        }
        for rank, row in enumerate(report["candidates"], 1):
            row["ranking_reason"] = (
                f"Rang {rank}: {len(row['confirmed_specific_clues'])} bestätigte Kernhinweise, "
                f"{len(row['hard_contradictions'])} harte Widersprüche, "
                f"Score {row['evidence_score']}; "
                "Widersprüche zuerst, danach spezifische Primärevidenz."
            )
            if row["cited_findings"]:
                row["ranking_reason"] += (
                    f" {len(row['cited_findings'])} vorläufige KI-Belegstellen; "
                    "keine unabhängige Primärbestätigung."
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
