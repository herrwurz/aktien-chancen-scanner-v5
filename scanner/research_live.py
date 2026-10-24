"""Bounded SEC collector for a teaser-independent normalized research snapshot."""

import hashlib

from scanner.research_facts import extract_sec_company_facts
from scanner.research_providers.sec_edgar import (
    normalize_submission_events,
    normalize_universe,
)
from scanner.research_snapshot import write_snapshot


def _sector(value):
    normalized = str(value or "").casefold()
    if "insurance" in normalized:
        return "insurance"
    if "bank" in normalized or "credit" in normalized:
        return "banking"
    if "pharmaceutical" in normalized:
        return "pharma"
    if "mining" in normalized:
        return "mining"
    if "electric" in normalized or "power" in normalized:
        return "energy"
    return None


def _rank(identity):
    return hashlib.sha256(f"sec-cik:{identity.cik}".encode()).hexdigest()


def collect_sec_snapshot(client, output, *, max_candidates):
    required = 1 + 2 * max_candidates
    if client.remaining < required:
        raise ValueError(f"SEC collector requires request limit of at least {required}")
    universe_record = client.fetch("universe")
    universe = normalize_universe(universe_record)
    issuers = {}
    for identity in sorted(universe, key=lambda row: (row.cik or "", row.ticker or "")):
        issuers.setdefault(identity.cik, identity)
    selected = sorted(issuers.values(), key=_rank)[:max_candidates]
    assets, events, facts = [], [], []
    records = [universe_record]
    errors = []
    for identity in selected:
        try:
            submissions = client.fetch("submissions", identity.cik)
        except ValueError:
            errors.append({"cik": identity.cik, "dataset": "submissions"})
            assets.append(identity)
            continue
        records.append(submissions)
        enriched = identity.model_copy(
            update={"sector": _sector(submissions["payload"].get("sicDescription"))}
        )
        assets.append(enriched)
        company_events = normalize_submission_events(submissions, enriched)
        events.extend(company_events)
        try:
            companyfacts = client.fetch("companyfacts", identity.cik)
        except ValueError:
            errors.append({"cik": identity.cik, "dataset": "companyfacts"})
            continue
        records.append(companyfacts)
        availability = {
            event.facts["accession_number"]: event.published_at for event in company_events
        }
        facts.extend(
            extract_sec_company_facts(
                companyfacts, enriched, availability_by_accession=availability
            )
        )
    raw_sources = [client.root / record["raw_file"] for record in records]
    coverage = {
        "kind": "real_archived",
        "provider": "SEC_EDGAR",
        "markets": ["US"],
        "universe_total": len(universe),
        "unique_issuer_total": len(issuers),
        "candidate_count": len(assets),
        "candidate_selection": "stable_sha256_cik_v1",
        "selection_independent_of_teaser": True,
        "network_request_limit": required,
        "cost_eur": 0,
        "limitations": [
            "bounded deterministic subset of SEC universe",
            "SEC filings are not general company news",
            "current SEC identity lookup is not historical identity proof",
        ],
        "errors": errors,
    }
    write_snapshot(
        output,
        assets=assets,
        events=events,
        facts=facts,
        coverage=coverage,
        raw_sources=raw_sources,
        generated_at=client.now(),
    )
    return {
        "status": "partial" if errors else "ok",
        "selection_method": coverage["candidate_selection"],
        "selected_count": len(assets),
        "universe_total": len(universe),
        "network_request_limit": required,
        "event_count": len(events),
        "fact_count": len(facts),
        "errors": errors,
    }
